import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import json
import keyboard  # Necessário: pip install keyboard

class VirtualMicApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Virtual Mic Overlay")
        self.root.geometry("400x600")
        
        # Configurações de Overlay
        self.root.attributes("-topmost", True)  # Sempre no topo
        self.root.attributes("-alpha", 0.9)     # Leve transparência
        
        # Configurações de arquivos
        self.config_file = "config.json"
        self.data = self.load_config()
        self.default_folder = self.data.get("default_folder", "")
        self.hotkeys = self.data.get("hotkeys", {}) # { "tecla": "nome_arquivo" }

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
            "hotkeys": self.hotkeys
        }
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)

    def setup_ui(self):
        # Estilo Dark/Compacto para Overlay
        style = ttk.Style()
        style.theme_use('clam')
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header com arraste (já que é overlay, facilita mover)
        title_label = ttk.Label(main_frame, text="VIRTUAL MIC OVERLAY", font=("Impact", 14))
        title_label.pack(pady=5)

        # Folder Config
        config_frame = ttk.Frame(main_frame)
        config_frame.pack(fill=tk.X, pady=2)
        ttk.Button(config_frame, text="📁 Pasta", command=self.change_default_folder, width=10).pack(side=tk.LEFT)
        self.device_list = self.get_output_devices()
        self.device_combo = ttk.Combobox(config_frame, values=[d['name'] for d in self.device_list], state="readonly", font=("Arial", 8))
        self.device_combo.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
        
        for i, d in enumerate(self.device_list):
            if "CABLE Input" in d['name'] or "Virtual" in d['name']:
                self.device_combo.current(i)
                break

        # Library
        lib_frame = ttk.LabelFrame(main_frame, text="Sons e Atalhos")
        lib_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.lib_listbox = tk.Listbox(lib_frame, bg="#222", fg="white", selectbackground="#444", font=("Arial", 9))
        self.lib_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.lib_listbox.bind('<<ListboxSelect>>', self.on_library_select)

        # Hotkey Info
        self.hotkey_label = ttk.Label(lib_frame, text="Atalho: Nenhum", font=("Arial", 8, "bold"))
        self.hotkey_label.pack()

        # Botões de Ação
        btn_grid = ttk.Frame(main_frame)
        btn_grid.pack(fill=tk.X)

        ttk.Button(btn_grid, text="Vincular Tecla", command=self.start_binding).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(btn_grid, text="Limpar Atalho", command=self.clear_hotkey).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Player Controls
        controls = ttk.Frame(main_frame)
        controls.pack(fill=tk.X, pady=10)

        self.vol_slider = ttk.Scale(controls, from_=0, to=2, orient=tk.HORIZONTAL, command=self.update_volume)
        self.vol_slider.set(1.0)
        self.vol_slider.pack(fill=tk.X)

        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

        self.play_btn = ttk.Button(main_frame, text="▶ PLAY", command=self.start_playback)
        self.play_btn.pack(fill=tk.X)
        
        self.stop_btn = ttk.Button(main_frame, text="■ STOP", command=self.stop_playback, state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X, pady=2)

    def get_output_devices(self):
        return [d for d in sd.query_devices() if d['max_output_channels'] > 0]

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
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(extensions)]
            for filename in files:
                full_path = os.path.join(folder_path, filename)
                self._add_to_memory(full_path, filename)
        except: pass

    def _add_to_memory(self, path, filename):
        try:
            data, rate = sf.read(path, always_2d=True)
            # Mostrar se tem hotkey no nome da lista
            display_name = filename
            for key, val in self.hotkeys.items():
                if val == filename:
                    display_name = f"[{key.upper()}] {filename}"
            
            self.audio_library[filename] = {"data": data, "rate": rate}
            self.lib_listbox.insert(tk.END, filename)
        except: pass

    def on_library_select(self, event):
        selection = self.lib_listbox.curselection()
        if selection:
            self.current_selected_key = self.lib_listbox.get(selection[0])
            # Achar se tem hotkey
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
        # Capturar próxima tecla
        threading.Thread(target=self._wait_for_key, daemon=True).start()

    def _wait_for_key(self):
        key = keyboard.read_event(suppress=True)
        if key.event_type == "down":
            key_name = key.name
            # Remover vinculo anterior dessa tecla se existir
            if key_name in self.hotkeys:
                del self.hotkeys[key_name]
            
            # Vincular nova
            self.hotkeys[key_name] = self.current_selected_key
            self.save_config()
            self.root.after(0, self.refresh_hotkeys)
            self.is_binding = False

    def clear_hotkey(self):
        if self.current_selected_key:
            keys_to_del = [k for k, v in self.hotkeys.items() if v == self.current_selected_key]
            for k in keys_to_del:
                del self.hotkeys[k]
            self.save_config()
            self.refresh_hotkeys()

    def refresh_hotkeys(self):
        keyboard.unhook_all()
        for key, filename in self.hotkeys.items():
            keyboard.add_hotkey(key, lambda f=filename: self.play_specific_audio(f))
        
        self.hotkey_label.config(text="Atalhos Atualizados!")
        if self.current_selected_key:
            current_hk = "Nenhum"
            for k, v in self.hotkeys.items():
                if v == self.current_selected_key:
                    current_hk = k.upper()
            self.hotkey_label.config(text=f"Atalho: {current_hk}")

    def play_specific_audio(self, filename):
        if filename in self.audio_library:
            self.current_selected_key = filename
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

import threading
if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualMicApp(root)
    root.mainloop()