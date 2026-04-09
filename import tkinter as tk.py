import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import json
import keyboard  # Necessário: pip install keyboard
import threading
import webbrowser

class VirtualMicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Virtual Mic Overlay")
        self.root.geometry("400x750")
        
        # Configurações de Overlay
        self.root.attributes("-topmost", True)  # Sempre no topo
        self.root.attributes("-alpha", 0.9)     # Leve transparência
        
        # Configurações de arquivos
        self.config_file = "config.json"
        self.data = self.load_config()
        self.default_folder = self.data.get("default_folder", "")
        self.hotkeys = self.data.get("hotkeys", {})  # { "tecla": "nome_arquivo" }
        self.global_hotkeys = self.data.get("global_hotkeys", {"play": "", "stop": ""})

        # State variables
        self.audio_library = {}
        self.current_selected_key = None
        self.is_playing = False
        self.stream = None
        self.volume = 1.0
        self.current_frame = 0
        self.is_binding = False

        self.setup_ui()
        
        if self.default_folder and os.path.exists(self.default_folder):
            self.load_folder_contents(self.default_folder)

        # Registrar hotkeys salvas
        self.refresh_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_config(self):
        config_data = {
            "default_folder": self.default_folder,
            "hotkeys": self.hotkeys,
            "global_hotkeys": self.global_hotkeys
        }
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)

    def setup_ui(self):
        # Estilo Dark/Compacto para Overlay
        style = ttk.Style()
        style.theme_use('clam')
        
        # Criação das Abas (Notebook)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.main_tab = ttk.Frame(self.notebook, padding="10")
        self.settings_tab = ttk.Frame(self.notebook, padding="10")
        self.about_tab = ttk.Frame(self.notebook, padding="10")

        self.notebook.add(self.main_tab, text="Biblioteca")
        self.notebook.add(self.settings_tab, text="Configurações")
        self.notebook.add(self.about_tab, text="Sobre")

        # --- ABA BIBLIOTECA ---
        title_label = ttk.Label(self.main_tab, text="VIRTUAL MIC OVERLAY", font=("Impact", 14))
        title_label.pack(pady=5)

        config_frame = ttk.Frame(self.main_tab)
        config_frame.pack(fill=tk.X, pady=2)
        ttk.Button(config_frame, text="📁 Pasta", command=self.change_default_folder, width=10).pack(side=tk.LEFT)
        
        self.device_list = self.get_output_devices()
        self.device_combo = ttk.Combobox(config_frame, values=[d['name'] for d in self.device_list], state="readonly", font=("Arial", 8))
        self.device_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
        
        for i, d in enumerate(self.device_list):
            if "CABLE Input" in d['name'] or "Virtual" in d['name']:
                self.device_combo.current(i)
                break

        # Botão MyInstants
        download_btn = ttk.Button(self.main_tab, text="🌐 Baixar Memes (MyInstants)", command=self.open_download_page)
        download_btn.pack(fill=tk.X, pady=5)

        lib_frame = ttk.LabelFrame(self.main_tab, text="Sons e Atalhos")
        lib_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.lib_listbox = tk.Listbox(lib_frame, bg="#222", fg="white", selectbackground="#444", font=("Arial", 9))
        self.lib_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.lib_listbox.bind('<<ListboxSelect>>', self.on_library_select)

        self.hotkey_label = ttk.Label(lib_frame, text="Atalho: Nenhum", font=("Arial", 8, "bold"))
        self.hotkey_label.pack()

        btn_grid = ttk.Frame(self.main_tab)
        btn_grid.pack(fill=tk.X)
        ttk.Button(btn_grid, text="Vincular Tecla", command=self.start_binding).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(btn_grid, text="Limpar Atalho", command=self.clear_hotkey).pack(side=tk.LEFT, fill=tk.X, expand=True)

        controls = ttk.Frame(self.main_tab)
        controls.pack(fill=tk.X, pady=10)
        self.vol_slider = ttk.Scale(controls, from_=0, to=2, orient=tk.HORIZONTAL, command=self.update_volume)
        self.vol_slider.set(1.0)
        self.vol_slider.pack(fill=tk.X)

        self.progress = ttk.Progressbar(self.main_tab, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

        self.play_btn = ttk.Button(self.main_tab, text="▶ PLAY", command=self.start_playback)
        self.play_btn.pack(fill=tk.X)
        self.stop_btn = ttk.Button(self.main_tab, text="■ STOP", command=self.stop_playback, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=2)

        # --- ABA CONFIGURAÇÕES ---
        ttk.Label(self.settings_tab, text="Atalhos Globais do Sistema", font=("Arial", 11, "bold")).pack(pady=10)
        
        # Play Global
        play_hk_frame = ttk.Frame(self.settings_tab)
        play_hk_frame.pack(fill=tk.X, pady=5)
        ttk.Label(play_hk_frame, text="Global PLAY:").pack(side=tk.LEFT)
        self.play_hk_btn = ttk.Button(play_hk_frame, text=self.global_hotkeys["play"] or "Definir", 
                                      command=lambda: self.start_global_binding("play"))
        self.play_hk_btn.pack(side=tk.RIGHT)

        # Stop Global
        stop_hk_frame = ttk.Frame(self.settings_tab)
        stop_hk_frame.pack(fill=tk.X, pady=5)
        ttk.Label(stop_hk_frame, text="Global STOP:").pack(side=tk.LEFT)
        self.stop_hk_btn = ttk.Button(stop_hk_frame, text=self.global_hotkeys["stop"] or "Definir", 
                                      command=lambda: self.start_global_binding("stop"))
        self.stop_hk_btn.pack(side=tk.RIGHT)

        ttk.Label(self.settings_tab, text="\nInstruções:", font=("Arial", 8, "bold")).pack(anchor=tk.W)
        instructions = (
            "- Clique no botão para definir a tecla.\n"
            "- A tecla Play tocará o som selecionado na lista.\n"
            "- A tecla Stop parará qualquer áudio imediatamente.\n"
            "- Esses atalhos funcionam fora do programa."
        )
        ttk.Label(self.settings_tab, text=instructions, font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W)

        # --- ABA ABOUT (SOBRE) ---
        about_title = ttk.Label(self.about_tab, text="Sobre o Programa", font=("Arial", 12, "bold"))
        about_title.pack(pady=10)

        desc_text = (
            "O Virtual Mic Overlay é uma ferramenta projetada para "
            "reproduzir áudios diretamente em dispositivos de entrada "
            "(Microfones Virtuais), permitindo o uso de memes e sons "
            "em jogos e programas de comunicação."
        )
        desc_label = ttk.Label(self.about_tab, text=desc_text, wraplength=350, justify=tk.LEFT)
        desc_label.pack(pady=5)

        features_frame = ttk.LabelFrame(self.about_tab, text="Principais Funcionalidades")
        features_frame.pack(fill=tk.X, pady=10)
        
        features_list = (
            "• Interface Overlay (Sempre no topo)\n"
            "• Atalhos Globais (Hotkeys) customizáveis\n"
            "• Integração direta com MyInstants\n"
            "• Controle de Volume e Progresso em tempo real\n"
            "• Suporte a múltiplos dispositivos de saída"
        )
        ttk.Label(features_frame, text=features_list, justify=tk.LEFT, padding=5).pack()

        # Info do Criador
        creator_frame = ttk.LabelFrame(self.about_tab, text="Desenvolvedor")
        creator_frame.pack(fill=tk.X, pady=10)

        info_grid = ttk.Frame(creator_frame, padding=5)
        info_grid.pack(fill=tk.X)

        self._create_info_row(info_grid, "Criador:", "Jonatas araujo", 0)
        self._create_info_row(info_grid, "Contato:", "araujojonatasapc152018@gmail.com", 1)
        self._create_info_row(info_grid, "WhatsApp:", "+55 71 98478-5356", 2)
        self._create_info_row(info_grid, "Localização:", "Salvador/BA - Brasil", 3)
        self._create_info_row(info_grid, "Data:", "09/04/2026", 4)
        
        # Link do GitHub com estilo
        github_btn = ttk.Button(self.about_tab, text="📂 Ver Perfil no GitHub", 
                                command=lambda: webbrowser.open("https://github.com/AlmiranteX"))
        github_btn.pack(fill=tk.X, pady=5)

    def _create_info_row(self, parent, label, value, row):
        ttk.Label(parent, text=label, font=("Arial", 8, "bold")).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Label(parent, text=value, font=("Arial", 8)).grid(row=row, column=1, sticky=tk.W, padx=10)

    def get_output_devices(self):
        return [d for d in sd.query_devices() if d['max_output_channels'] > 0]

    def open_download_page(self):
        """Abre o site MyInstants no navegador padrão."""
        url = "https://www.myinstants.com/pt/search/?name=meme"
        webbrowser.open(url)

    def change_default_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.default_folder = folder
            self.save_config()
            self.load_folder_contents(folder)

    def load_folder_contents(self, folder_path):
        self.lib_listbox.delete(0, tk.END)
        self.audio_library.clear()
        extensions = ('.wav', '.mp3', '.flac', '.ogg')
        try:
            files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(extensions)])
            for filename in files:
                full_path = os.path.join(folder_path, filename)
                self._add_to_memory(full_path, filename)
        except: pass

    def _add_to_memory(self, path, filename):
        try:
            data, rate = sf.read(path, always_2d=True)
            self.audio_library[filename] = {"data": data, "rate": rate}
            self.lib_listbox.insert(tk.END, filename)
        except: pass

    def on_library_select(self, event):
        selection = self.lib_listbox.curselection()
        if selection:
            self.current_selected_key = self.lib_listbox.get(selection[0])
            current_hk = "Nenhum"
            for k, v in self.hotkeys.items():
                if v == self.current_selected_key:
                    current_hk = k.upper()
            self.hotkey_label.config(text=f"Atalho: {current_hk}")

    def start_binding(self):
        if not self.current_selected_key:
            messagebox.showinfo("Overlay", "Selecione um som na lista primeiro.")
            return
        self.is_binding = True
        self.hotkey_label.config(text="PRESSIONE UMA TECLA...")
        threading.Thread(target=self._wait_for_key, daemon=True).start()

    def _wait_for_key(self):
        key = keyboard.read_event(suppress=True)
        if key.event_type == "down":
            key_name = key.name
            if key_name in self.hotkeys:
                del self.hotkeys[key_name]
            self.hotkeys[key_name] = self.current_selected_key
            self.save_config()
            self.root.after(0, self.refresh_hotkeys)
            self.is_binding = False

    def start_global_binding(self, action):
        def _wait():
            self.root.after(0, lambda: self.play_hk_btn.config(text="..." if action == "play" else self.play_hk_btn["text"]))
            self.root.after(0, lambda: self.stop_hk_btn.config(text="..." if action == "stop" else self.stop_hk_btn["text"]))
            
            key = keyboard.read_event(suppress=True)
            if key.event_type == "down":
                self.global_hotkeys[action] = key.name
                self.save_config()
                self.root.after(0, self.refresh_hotkeys)
                self.root.after(0, lambda: self.play_hk_btn.config(text=self.global_hotkeys["play"].upper() or "Definir"))
                self.root.after(0, lambda: self.stop_hk_btn.config(text=self.global_hotkeys["stop"].upper() or "Definir"))

        threading.Thread(target=_wait, daemon=True).start()

    def clear_hotkey(self):
        if self.current_selected_key:
            keys_to_del = [k for k, v in self.hotkeys.items() if v == self.current_selected_key]
            for k in keys_to_del:
                del self.hotkeys[k]
            self.save_config()
            self.refresh_hotkeys()

    def refresh_hotkeys(self):
        keyboard.unhook_all()
        
        # Hotkeys de sons específicos
        for key, filename in self.hotkeys.items():
            keyboard.add_hotkey(key, lambda f=filename: self.play_specific_audio(f))
        
        # Hotkeys Globais (Play/Stop)
        if self.global_hotkeys.get("play"):
            keyboard.add_hotkey(self.global_hotkeys["play"], self.start_playback)
        if self.global_hotkeys.get("stop"):
            keyboard.add_hotkey(self.global_hotkeys["stop"], self.stop_playback)
            
        if self.current_selected_key:
            current_hk = "Nenhum"
            for k, v in self.hotkeys.items():
                if v == self.current_selected_key:
                    current_hk = k.upper()
            self.hotkey_label.config(text=f"Atalho: {current_hk}")

    def play_specific_audio(self, filename):
        if filename in self.audio_library:
            self.current_selected_key = filename
            # Selecionar visualmente na lista se possível
            items = self.lib_listbox.get(0, tk.END)
            if filename in items:
                idx = items.index(filename)
                self.lib_listbox.selection_clear(0, tk.END)
                self.lib_listbox.selection_set(idx)
                self.lib_listbox.see(idx)
            self.root.after(0, self.start_playback)

    def update_volume(self, val):
        self.volume = float(val)

    def audio_callback(self, outdata, frames, time, status):
        if not self.is_playing or self.current_selected_key not in self.audio_library:
            outdata.fill(0)
            return

        audio_info = self.audio_library[self.current_selected_key]
        data = audio_info["data"]
        chunksize = min(len(data) - self.current_frame, frames)
        
        out_ch = outdata.shape[1]
        in_ch = data.shape[1]
        chunk = data[self.current_frame:self.current_frame + chunksize] * self.volume
        
        if in_ch == out_ch:
            outdata[:chunksize] = chunk
        else:
            for i in range(out_ch):
                outdata[:chunksize, i] = chunk[:, i % in_ch]
        
        if chunksize < frames:
            outdata[chunksize:] = 0
            self.is_playing = False
            self.root.after(10, self.stop_playback)
        
        self.current_frame += chunksize
        self.root.after(0, lambda p=(self.current_frame/len(data))*100: self.progress.configure(value=p))

    def start_playback(self):
        self.stop_playback()
        if not self.current_selected_key or self.current_selected_key not in self.audio_library: return

        idx = self.device_combo.current()
        if idx == -1: return

        target = self.device_list[idx]['index']
        info = self.audio_library[self.current_selected_key]
        
        self.current_frame = 0
        self.is_playing = True
        self.play_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        try:
            self.stream = sd.OutputStream(
                samplerate=info["rate"], device=target,
                channels=self.device_list[idx]['max_output_channels'],
                callback=self.audio_callback, blocksize=1024
            )
            self.stream.start()
        except: self.stop_playback()

    def stop_playback(self):
        self.is_playing = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except: pass
            self.stream = None
        self.play_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0

    def on_closing(self):
        keyboard.unhook_all()
        self.is_playing = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualMicApp(root)
    root.mainloop()