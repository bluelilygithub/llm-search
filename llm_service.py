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
        
        # Initialize Anthropic for direct HTTP requests
        self.anthropic_available = False
        self.claude_key = os.getenv('CLAUDE_API_KEY')
        if self.claude_key:
            self.anthropic_available = True
            print("Anthropic API key configured for direct HTTP requests")
        else:
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
        """Get response from specified LLM model. Returns (response_text, tokens, estimated_cost)"""
        # Map legacy Gemini model names to current names
        GEMINI_MODEL_MAP = {
            'gemini-pro': 'models/gemini-1.5-pro-002',
            'gemini-flash': 'models/gemini-1.0-flash-latest',
            'models/gemini-pro': 'models/gemini-1.5-pro-002',
            'models/gemini-flash': 'models/gemini-1.0-flash-latest'
        }
        if model in GEMINI_MODEL_MAP:
            model = GEMINI_MODEL_MAP[model]
        if model.startswith('gpt') or model.startswith('o1'):
            return self._get_openai_response(model, messages, max_tokens, temperature)
        elif model.startswith('claude'):
            return self._get_anthropic_response(model, messages, max_tokens, temperature)
        elif model.startswith('models/gemini'):
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
            # Calculate rough token count to prevent silent failures
            total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
            estimated_tokens = total_chars // 3  # Rough estimate: 3 chars per token
            
            print(f"OpenAI request: model={model}, estimated_tokens={estimated_tokens}, max_tokens={max_tokens}")
            
            # Check if we're likely to exceed limits
            model_limits = self.get_model_limits(model)
            if estimated_tokens + max_tokens > model_limits['context_window']:
                raise Exception(f"Request too large for {model}. Estimated {estimated_tokens} tokens, max allowed {model_limits['context_window']}. Try using Gemini Pro or Claude for large documents.")
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            text = response.choices[0].message.content
            tokens = response['usage']['total_tokens'] if 'usage' in response else 0
            # Example pricing (update as needed):
            # gpt-4: $0.03/1K prompt, $0.06/1K completion; gpt-3.5: $0.001/1K
            if model.startswith('gpt-4'):
                cost = tokens * 0.00006  # $0.06/1K tokens (rough estimate)
            elif model.startswith('gpt-3.5'):
                cost = tokens * 0.000002  # $0.002/1K tokens
            else:
                cost = tokens * 0.00002  # fallback
            return text, tokens, cost
        except Exception as e:
            print(f"OpenAI API detailed error: {type(e).__name__}: {str(e)}")
            raise Exception(f"OpenAI API error: {str(e)}")
    
    def _get_anthropic_response(self, model, messages, max_tokens, temperature):
        """Get response from Anthropic Claude models using direct HTTP requests."""
        if not self.anthropic_available or not self.claude_key:
            raise Exception("Anthropic API key not configured")
        claude_models = [
            'claude-sonnet-4-20250514',
            'claude-opus-4',
            'claude-3-5-sonnet-20241022',
            'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'claude-3.5-sonnet-20240620',
            'claude-3-haiku-20240307'
        ]
        try_models = [model] + [m for m in claude_models if m != model]
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
        last_error = None
        for try_model in try_models:
            try:
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.claude_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": try_model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "system": system_message or "You are a helpful AI assistant.",
                        "messages": anthropic_messages
                    },
                    timeout=15
                )
                data = resp.json()
                if resp.ok and data.get('content') and data['content'][0].get('text'):
                    text = data['content'][0]['text']
                    # Anthropic API may return usage info in 'usage' or 'usage_metadata'
                    tokens = 0
                    if 'usage' in data and 'output_tokens' in data['usage']:
                        tokens = data['usage']['output_tokens']
                    elif 'usage_metadata' in data and 'output_tokens' in data['usage_metadata']:
                        tokens = data['usage_metadata']['output_tokens']
                    # Example pricing: Claude 3 Sonnet $3/1M, Opus $15/1M, Haiku $0.25/1M
                    if 'sonnet' in try_model:
                        cost = tokens * 0.003  # $3/1M tokens
                    elif 'opus' in try_model:
                        cost = tokens * 0.015  # $15/1M tokens
                    elif 'haiku' in try_model:
                        cost = tokens * 0.00025  # $0.25/1M tokens
                    else:
                        cost = tokens * 0.003
                    return text, tokens, cost
                else:
                    last_error = data
            except Exception as e:
                last_error = str(e)
                continue
        raise Exception(f"Anthropic API error: All models failed. Last error: {last_error}")
    
    def _get_gemini_response(self, model, messages, max_tokens, temperature):
        if not self.gemini_available:
            raise Exception("Gemini API key not configured")
        try:
            prompt = '\n'.join([f"{m['role']}: {m['content']}" for m in messages])
            model_obj = genai.GenerativeModel(model)
            response = model_obj.generate_content(prompt, generation_config={"max_output_tokens": max_tokens, "temperature": temperature})
            text = response.text if hasattr(response, 'text') else str(response)
            tokens = 0
            if hasattr(response, 'usage_metadata') and hasattr(response.usage_metadata, 'total_tokens'):
                tokens = response.usage_metadata.total_tokens
            cost = tokens * 0.00025
            return text, tokens, cost
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
                text = result[0].get('generated_text', 'No response generated')
                # Hugging Face free models do not return token usage or cost
                tokens = 0
                cost = 0.0
                return text, tokens, cost
            else:
                return str(result), 0, 0.0
                
        except Exception as e:
            raise Exception(f"Hugging Face API error: {str(e)}")
    
    def get_model_limits(self, model):
        """Get practical token limits for different models"""
        limits = {
            # OpenAI Models - Updated to practical limits
            'gpt-4': {'max_tokens': 4000, 'context_window': 8000},  # Reduced for safety
            'gpt-4-turbo': {'max_tokens': 4000, 'context_window': 120000},
            'gpt-3.5-turbo': {'max_tokens': 2000, 'context_window': 14000},  # Conservative
            'o1-preview': {'max_tokens': 8000, 'context_window': 120000},
            'o1-mini': {'max_tokens': 8000, 'context_window': 120000},
            
            # Anthropic Claude Models - High capacity
            'claude-3-opus': {'max_tokens': 4000, 'context_window': 180000},
            'claude-3-sonnet': {'max_tokens': 4000, 'context_window': 180000}, 
            'claude-3-haiku': {'max_tokens': 4000, 'context_window': 180000},
            'claude-3.5-sonnet': {'max_tokens': 8000, 'context_window': 180000},
            'claude-sonnet-4-20250514': {'max_tokens': 8000, 'context_window': 180000},
            'claude-3-5-sonnet-20241022': {'max_tokens': 8000, 'context_window': 180000},
            
            # Google Gemini Models - Highest capacity
            'gemini-pro': {'max_tokens': 8000, 'context_window': 900000},
            'gemini-flash': {'max_tokens': 8000, 'context_window': 900000},
            'gemini-1.5-pro': {'max_tokens': 8000, 'context_window': 2000000},
            'gemini-1.5-flash': {'max_tokens': 8000, 'context_window': 1000000},
            
            # Hugging Face Models - Limited
            'llama2-70b': {'max_tokens': 2000, 'context_window': 3000},
            'mixtral-8x7b': {'max_tokens': 3000, 'context_window': 30000}, 
            'codellama-34b': {'max_tokens': 3000, 'context_window': 14000}
        }
        return limits.get(model, {'max_tokens': 2000, 'context_window': 6000})
    
    def format_conversation_for_llm(self, messages):
        """Convert database messages to LLM API format"""
        formatted_messages = []
        
        for msg in messages:
            formatted_messages.append({
                'role': msg.role,
                'content': msg.content
            })
            
        return formatted_messages