import tkinter as tk
from tkinter import DISABLED
import customtkinter
from llama_cpp import Llama
import pyttsx3
import os
import json
import spacy
import weaviate
import threading
import base64  # Import the base64 library for encoding

# Initialize Weaviate client
client = weaviate.Client("http://localhost:8080")

# Initialize the text-to-speech engine
engine = pyttsx3.init()

# Initialize spaCy model
nlp = spacy.load("en_core_web_sm")

# Function to handle text-to-speech
def speak_text(text):
    engine.say(text)
    engine.runAndWait()

# Initialize Llama model
script_dir = os.path.dirname(os.path.realpath(__file__))
model_path = os.path.join(script_dir, "llama-2-7b.ggmlv3.q8_0.bin")
llm = Llama(model_path=model_path, n_ctx=3925)

# Function to get context from Weaviate
def get_context_from_weaviate(issue_concepts):
    try:
        response = client.query.get('VehicleRepair', ['issue', 'solution', 'tools_needed']).with_near_text({'concepts': issue_concepts}).do()
        if response['data']['Get']['VehicleRepair']:
            return response['data']['Get']['VehicleRepair'][0]
        else:
            return None
    except Exception as e:
        print(f"Error fetching context from Weaviate: {e}")
        return None

# Function to extract relevant keywords from the user's input
def extract_keywords(user_input):
    doc = nlp(user_input)
    dynamic_keywords = [token.lemma_ for token in doc if token.pos_ in ["NOUN", "VERB"]]
    static_keywords = ['fix', 'repair', 'help', 'solve', 'complete', 'find']
    combined_keywords = list(set(dynamic_keywords + static_keywords))
    return combined_keywords

# Function to generate text from Llama model with chunking and error handling
def llama_generate(prompt, text_box):
    try:
        # Extract keywords and get context from Weaviate
        issue_concepts = extract_keywords(prompt)
        repair_data = get_context_from_weaviate(issue_concepts)
        
        if repair_data:
            weaviate_context = f"Based on the data, the issue is {repair_data['issue']}. The solution is {repair_data['solution']} and the tools needed are {repair_data['tools_needed']}."
        else:
            weaviate_context = "No relevant data found."
        
        # Knowledge Injection
        context_string = f"Context: This is a conversation with an AI model to generate text. {weaviate_context}"
        prompt = f"{context_string} {prompt}"
        
        # Define a delimiter for chunk linking
        delimiter = "reppinisa4wordpingoeshere"
        
        # Encode the delimiter using base64
        encoded_delimiter = base64.b64encode(delimiter.encode()).decode()
        
        # Initialize a counter for generating unique but sequential PINs
        counter = 0
        
        # Dynamic Chunk Size
        max_tokens = min(655, len(prompt))
        
        # Context Preservation (simple example)
        if '.' in prompt[max_tokens-10:max_tokens]:
            max_tokens = prompt.rfind('.', 0, max_tokens) + 1
        
        # Chunking logic with overlap
        overlap = 10  # Overlap of 10 tokens
        chunks = [prompt[i:i + max_tokens] for i in range(0, len(prompt), max_tokens - overlap)]
        
        for chunk in chunks:
            # Increment the counter
            counter += 1
            
            # Generate a unique but sequential PIN
            pin = f"PIN{counter}"
            
            # Add the encoded delimiter and PIN to the chunk
            chunk_with_delimiter = f"{encoded_delimiter}{pin}{chunk}{encoded_delimiter}{pin}"
            
            try:
                # Generate the output from Llama model
                output = llm(chunk_with_delimiter, max_tokens=max_tokens)
                
                # Error Recovery
                error_keywords = ["error", "undefined", "null"]  # Define your own error keywords
                if any(keyword in output.lower() for keyword in error_keywords):
                    print("Error keyword detected. Regenerating chunk...")
                    output = llm(chunk_with_delimiter, max_tokens=max_tokens)  # Regenerate
                
                # Update the text box
                text_box.after(0, lambda: update_textbox(text_box, output))
                
            except Exception as inner_e:
                print(f"Error in Llama model or text box update: {inner_e}")
                
    except Exception as e:
        print(f"General error generating response: {e}")



# Function to update the text box
def update_textbox(text_box, output):
    text_box.configure(state="normal")
    text_box.insert(tk.END, f"AI: {output}\n")
    text_box.see(tk.END)
    text_box.config(state=DISABLED)
    speak_text(output)

# Main App class
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

        self.initialize_games()

        self.text_box = customtkinter.CTkTextbox(
            self,
            width=50,
            height=20,
            font=("TkDefaultFont", 16),
            state=DISABLED
        )
        self.text_box.grid(row=0, column=1, rowspan=3, columnspan=3, padx=(20, 20), pady=(20, 20), sticky="nsew")
        
        self.entry = customtkinter.CTkEntry(
            self,
            font=("TkDefaultFont", 16),
            justify="left"
        )
        self.entry.grid(row=3, column=1, columnspan=2, padx=(20, 0), pady=(20, 10), sticky="nsew")
        
        self.send_button = customtkinter.CTkButton(
            self,
            text="Send",
            command=self.on_submit
        )
        self.send_button.grid(row=3, column=3, padx=(0, 20), pady=(20, 10), sticky="nsew")
        
        self.entry.bind('<Return>', self.on_submit)
        self.current_game = None
        self.current_prompt_index = 0

    def on_submit(self, event=None):
        message = self.entry.get().strip()
        if message:
            self.entry.delete(0, tk.END)
            self.text_box.configure(state="normal")
            self.text_box.insert(tk.END, f"You: {message}\n")
            self.text_box.see(tk.END)
            self.text_box.configure(state=DISABLED)
            prompt = f"User said: {message} ((((((LASTMSG)))))"
            threading.Thread(target=llama_generate, args=(prompt, self.text_box)).start()

    def initialize_games(self):
        try:
            with open("configurations.json", "r") as config_file:
                data = json.load(config_file)
            self.config_data = data["configurations"]

            self.config_buttons = []
            for config_key in self.config_data.keys():
                config_button = customtkinter.CTkButton(self.sidebar_frame, text=config_key, command=lambda k=config_key: self.select_game(k))
                config_button.grid(row=len(self.config_buttons), column=0, padx=20, pady=10, sticky="nsew")
                self.config_buttons.append(config_button)

        except Exception as e:
            print(f"Error loading configurations: {e}")

    def select_game(self, config_key):
        self.current_config = self.config_data[config_key]
        initial_prompt = self.current_config.get('initial_prompt_rules', '')
        system_message = self.current_config.get('system_message_content', '')

        self.text_box.configure(state="normal")
        self.text_box.insert(tk.END, f"System: {system_message}\n")
        self.text_box.see(tk.END)
        self.text_box.configure(state=DISABLED)

        threading.Thread(target=speak_text, args=(system_message,)).start()
        threading.Thread(target=llama_generate, args=(initial_prompt, self.text_box)).start()

if __name__ == "__main__":
    app = App()
    app.mainloop()
