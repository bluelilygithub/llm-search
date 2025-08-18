import openai
import anthropic
import google.generativeai as genai
import requests
from config import Config
import os

class LLMService:
    def __init__(self):
        # Initialize all availability flags
        self.openai_available = False
        self.anthropic_available = False
        self.gemini_available = False
        
        # Initialize OpenAI (v0.28 style - no client object)
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            openai.api_key = openai_key
            self.openai_available = True
            print("OpenAI API key configured")
        
        # Initialize Anthropic client 
        claude_key = os.getenv('CLAUDE_API_KEY')
        if claude_key:
            self.anthropic_client = anthropic.Anthropic(api_key=claude_key)
            self.anthropic_available = True
            print("Anthropic client initialized")
        else:
            self.anthropic_available = False
            print("No Claude API key found")
        
        # Initialize Gemini safely
        gemini_key = os.getenv('GEMINI_API_KEY')
        if gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_available = True
                print("Gemini configured")
            except Exception as e:
                print(f"Gemini failed: {e}")
                self.gemini_available = False
        
        # Initialize Hugging Face
        self.hf_api_key = os.getenv('HUGGING_FACE_API_KEY')
        if self.hf_api_key:
            self.hf_headers = {"Authorization": f"Bearer {self.hf_api_key}"}
            self.hf_available = True
            print("Hugging Face configured")
        else:
            self.hf_available = False
        
    def get_response(self, model, messages, max_tokens=4000, temperature=0.7):
        """Get response from specified LLM model"""
        
        if model.startswith('gpt') or model.startswith('o1'):
            return self._get_openai_response(model, messages, max_tokens, temperature)
        elif model.startswith('claude'):
            return self._get_anthropic_response(model, messages, max_tokens, temperature)
        elif model.startswith('gemini'):
            return self._get_gemini_response(model, messages, max_tokens, temperature)
        elif model in ['llama2-70b', 'mixtral-8x7b', 'codellama-34b']:
            return self._get_huggingface_response(model, messages, max_tokens, temperature)
        else:
            raise ValueError(f"Model {model} not available")
    
    def _get_openai_response(self, model, messages, max_tokens, temperature):
        """Get response from OpenAI models"""
        if not self.openai_available:
            raise Exception("OpenAI API key not configured")
            
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _get_anthropic_response(self, model, messages, max_tokens, temperature):
        """Get response from Anthropic Claude models"""
        if not self.anthropic_available:
            raise Exception("Anthropic API key not configured")
            
        try:
            # Convert messages format for Anthropic
            anthropic_messages = []
            system_message = None
            
            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    anthropic_messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })
            
            # Map model names
            model_mapping = {
                'claude-3-opus': 'claude-3-opus-20240229',
                'claude-3-sonnet': 'claude-3-sonnet-20240229',
                'claude-3.5-sonnet': 'claude-3-5-sonnet-20240620',
                'claude-3-haiku': 'claude-3-haiku-20240307'
            }
            
            mapped_model = model_mapping.get(model, model)
            
            response = self.anthropic_client.messages.create(
                model=mapped_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message or "You are a helpful AI assistant.",
                messages=anthropic_messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
    def _get_gemini_response(self, model, messages, max_tokens, temperature):
        """Get response from Google Gemini models"""
        if not self.gemini_available:
            raise Exception("Gemini API key not configured")
            
        try:
            # Map model names
            model_mapping = {
                'gemini-pro': 'gemini-1.5-pro',
                'gemini-flash': 'gemini-1.5-flash'
            }
            
            mapped_model = model_mapping.get(model, model)
            model_instance = genai.GenerativeModel(mapped_model)
            
            # Convert messages to Gemini format
            conversation_text = ""
            for msg in messages:
                role = "Human" if msg['role'] == 'user' else "Assistant"
                conversation_text += f"{role}: {msg['content']}\n\n"
            
            response = model_instance.generate_content(
                conversation_text,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            
            return response.text
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def _get_huggingface_response(self, model, messages, max_tokens, temperature):
        """Get response from Hugging Face models"""
        if not self.hf_available:
            raise Exception("Hugging Face API key not configured")
            
        try:
            # Map model names to HF endpoints
            model_mapping = {
                'llama2-70b': 'meta-llama/Llama-2-70b-chat-hf',
                'mixtral-8x7b': 'mistralai/Mixtral-8x7B-Instruct-v0.1',
                'codellama-34b': 'codellama/CodeLlama-34b-Instruct-hf'
            }
            
            hf_model = model_mapping.get(model, model)
            
            # Format conversation for HF
            conversation_text = ""
            for msg in messages:
                role = msg['role'].capitalize()
                conversation_text += f"{role}: {msg['content']}\n\n"
            
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{hf_model}",
                headers=self.hf_headers,
                json={
                    "inputs": conversation_text,
                    "parameters": {
                        "max_new_tokens": max_tokens,
                        "temperature": temperature,
                        "return_full_text": False
                    }
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"HF API returned {response.status_code}: {response.text}")
            
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('generated_text', 'No response generated')
            else:
                return str(result)
                
        except Exception as e:
            raise Exception(f"Hugging Face API error: {str(e)}")
    
    def get_model_limits(self, model):
        """Get token limits for different models"""
        limits = {
            # OpenAI Models
            'gpt-4': {'max_tokens': 8192, 'context_window': 128000},
            'gpt-4-turbo': {'max_tokens': 4096, 'context_window': 128000},
            'gpt-3.5-turbo': {'max_tokens': 4096, 'context_window': 16385},
            'o1-preview': {'max_tokens': 32768, 'context_window': 128000},
            'o1-mini': {'max_tokens': 65536, 'context_window': 128000},
            
            # Anthropic Claude Models
            'claude-3-opus': {'max_tokens': 4096, 'context_window': 200000},
            'claude-3-sonnet': {'max_tokens': 4096, 'context_window': 200000},
            'claude-3-haiku': {'max_tokens': 4096, 'context_window': 200000},
            'claude-3.5-sonnet': {'max_tokens': 8192, 'context_window': 200000},
            
            # Google Gemini Models
            'gemini-pro': {'max_tokens': 8192, 'context_window': 1000000},
            'gemini-flash': {'max_tokens': 8192, 'context_window': 1000000},
            
            # Hugging Face Models
            'llama2-70b': {'max_tokens': 4096, 'context_window': 4096},
            'mixtral-8x7b': {'max_tokens': 4096, 'context_window': 32768},
            'codellama-34b': {'max_tokens': 4096, 'context_window': 16384}
        }
        return limits.get(model, {'max_tokens': 4000, 'context_window': 8000})
    
    def format_conversation_for_llm(self, messages):
        """Convert database messages to LLM API format"""
        formatted_messages = []
        
        for msg in messages:
            formatted_messages.append({
                'role': msg.role,
                'content': msg.content
            })
            
        return formatted_messages