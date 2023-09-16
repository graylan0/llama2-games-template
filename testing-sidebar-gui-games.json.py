import tkinter as tk
from tkinter import DISABLED
import customtkinter
from llama_cpp import Llama
import pyttsx3
import os
import json
import threading

# Initialize the text-to-speech engine
engine = pyttsx3.init()

# Public Function: Handles text-to-speech
def speak_text(text):
    """Speak the given text."""
    engine.say(text)
    engine.runAndWait()

# Initialize Llama model
_script_dir = os.path.dirname(os.path.realpath(__file__))
_model_path = os.path.join(_script_dir, "llama-2-7b.ggmlv3.q8_0.bin")
llm = Llama(model_path=_model_path, n_ctx=125)

# Private Function: Save data to JSON file
def _save_to_json(data, filename):
    """Save data to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving to JSON: {e}")

# Private Function: Load data from JSON file
def _load_from_json(filename):
    """Load data from a JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error loading from JSON: {e}")
        return []

# Public Function: Generate text with Llama in chunks
def llama_generate_with_chunking(prompt, text_box, max_tokens=125, overlap=20):
    """Generate text using the Llama model in chunks."""
    history = _load_from_json('history.json')
    thoughts = _load_from_json('thinking.json')

    history.append(prompt)
    thoughts.append(f"Thinking about: {prompt}")

    _save_to_json(history, 'history.json')
    _save_to_json(thoughts, 'thinking.json')

    tokens = prompt.split()
    start_idx = 0
    end_idx = max_tokens
    output = ""

    while start_idx < len(tokens):
        history = _load_from_json('history.json')
        thoughts = _load_from_json('thinking.json')

        chunk = " ".join(tokens[start_idx:end_idx])
# Inside the while loop in the llama_generate_with_chunking function
        try:
            chunk_output = llm(chunk, max_tokens=max_tokens)
            if isinstance(chunk_output, dict):
                if 'text' in chunk_output:  # Replace 'text' with the actual key if it's different
                    chunk_output = chunk_output['text']
                else:
                    chunk_output = "Unknown output format."
        except Exception as e:
            print(f"Error generating text: {e}")
            chunk_output = "Error generating text."

        output += str(chunk_output)  # Convert to string just to be safe
        history.append(chunk_output)
        thoughts.append(f"Generated: {chunk_output}")

        _save_to_json(history, 'history.json')
        _save_to_json(thoughts, 'thinking.json')

        start_idx = end_idx - overlap
        end_idx = start_idx + max_tokens

    text_box.after(0, lambda: _update_textbox(text_box, output))


# Private Function: Update the text box
def _update_textbox(text_box, output):
    """Update the text box with generated text."""
    text_box.configure(state="normal")
    text_box.insert(tk.END, f"AI: {output}\n")
    text_box.see(tk.END)
    text_box.config(state=DISABLED)
    speak_text(output)

# Tkinter Application Class
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Conversation Game")
        self.geometry(f"{1820}x{880}")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0, 1, 2), weight=1)
        
        # Create a frame for the sidebar
        self.sidebar_frame = customtkinter.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # Initialize games
        self.initialize_games()

        # Create text box
        self.text_box = customtkinter.CTkTextbox(
            self,
            width=50,
            height=20,
            font=("TkDefaultFont", 16),
            state=DISABLED
        )
        self.text_box.grid(row=0, column=1, rowspan=3, columnspan=3, padx=(20, 20), pady=(20, 20), sticky="nsew")
        
        # Create entry box
        self.entry = customtkinter.CTkEntry(
            self,
            font=("TkDefaultFont", 16),
            justify="left"
        )
        self.entry.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=(20, 10), sticky="nsew")
        
        # Create send button
        self.send_button = customtkinter.CTkButton(
            self,
            text="Send",
            command=self.on_submit
        )
        self.send_button.grid(row=3, column=3, padx=(0, 20), pady=(20, 10), sticky="nsew")
        
        # Bind enter key to submit
        self.entry.bind('<Return>', self.on_submit)

    def on_submit(self, event=None):
        """Handle the submit event."""
        message = self.entry.get().strip()
        if message:
            self.entry.delete(0, tk.END)
            self.text_box.configure(state="normal")
            self.text_box.insert(tk.END, f"You: {message}\n")
            self.text_box.see(tk.END)
            self.text_box.configure(state=DISABLED)
            prompt = f"User said: {message}"
            threading.Thread(target=llama_generate_with_chunking, args=(prompt, self.text_box)).start()

    def initialize_games(self):
        """Initialize the games."""
        try:
            with open("games.json", "r") as games_file:
                data = json.load(games_file)
            self.games_data = data["games"]
            self.game_buttons = []
            for idx, game in enumerate(self.games_data):
                game_button = customtkinter.CTkButton(self.sidebar_frame, text=game["title"], command=lambda i=idx: self.select_game(i))
                game_button.grid(row=idx, column=0, padx=20, pady=10, sticky="nsew")
                self.game_buttons.append(game_button)
        except Exception as e:
            print(f"Error loading games: {e}")

    def select_game(self, game_idx):
        """Select a game."""
        self.current_game = self.games_data[game_idx]
        first_prompt = self.current_game.get('prompts', [])[0]
        self.text_box.configure(state="normal")
        self.text_box.insert(tk.END, f"Game: {first_prompt}\n")
        self.text_box.see(tk.END)
        self.text_box.configure(state=DISABLED)
        threading.Thread(target=speak_text, args=(first_prompt,)).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
