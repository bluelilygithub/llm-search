from openai import OpenAI
import anthropic
import google.generativeai as genai
import requests
from config import Config
import os
import logging

class LLMService:
    def __init__(self):
        # Initialize logger
        self.logger = logging.getLogger('llm_service')
        
        # Initialize all availability flags
        self.openai_available = False
        self.anthropic_available = False
        self.gemini_available = False
        
        # Initialize OpenAI (v1.x style - client object)
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            self.openai_client = OpenAI(api_key=openai_key)
            self.openai_available = True
            self.logger.info("OpenAI API key configured")
        else:
            self.openai_client = None
        
        # Initialize Anthropic for direct HTTP requests
        self.anthropic_available = False
        self.claude_key = os.getenv('CLAUDE_API_KEY')
        if self.claude_key:
            self.anthropic_available = True
            self.logger.info("Anthropic API key configured")
        else:
            self.logger.warning("No Claude API key found")
        
        # Initialize Gemini safely
        gemini_key = os.getenv('GEMINI_API_KEY')
        if gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_available = True
                self.logger.info("Gemini API key configured")
            except Exception as e:
                self.logger.error(f"Gemini configuration failed: {e}")
                self.gemini_available = False
        
        # Initialize Hugging Face
        self.hf_api_key = os.getenv('HUGGING_FACE_API_KEY')
        if self.hf_api_key:
            self.hf_headers = {"Authorization": f"Bearer {self.hf_api_key}"}
            self.hf_available = True
            self.logger.info("Hugging Face API key configured")
        else:
            self.hf_available = False
            
        # Initialize Stability AI
        self.stability_api_key = os.getenv('STABILITY_API_KEY')
        if self.stability_api_key:
            self.stability_headers = {"Authorization": f"Bearer {self.stability_api_key}"}
            self.stability_available = True
            self.logger.info("Stability AI API key configured")
        else:
            self.stability_available = False
        
    def get_response(self, model, messages, max_tokens=4000, temperature=0.7, is_authenticated=False):
        """Get response from specified LLM model. Returns (response_text, tokens, estimated_cost)"""
        # Map legacy Gemini model names to current names
        GEMINI_MODEL_MAP = {
            'gemini-pro': 'models/gemini-1.5-pro-002',
            'gemini-flash': 'models/gemini-1.5-flash-latest',
            'models/gemini-pro': 'models/gemini-1.5-pro-002',
            'models/gemini-flash': 'models/gemini-1.5-flash-latest'
        }
        if model in GEMINI_MODEL_MAP:
            model = GEMINI_MODEL_MAP[model]
        if model.startswith('gpt') or model.startswith('o1'):
            return self._get_openai_response(model, messages, max_tokens, temperature, is_authenticated)
        elif model.startswith('claude'):
            return self._get_anthropic_response(model, messages, max_tokens, temperature)
        elif model.startswith('models/gemini'):
            return self._get_gemini_response(model, messages, max_tokens, temperature)
        elif model in ['llama2-70b', 'mixtral-8x7b', 'codellama-34b']:
            return self._get_huggingface_response(model, messages, max_tokens, temperature)
        elif model in ['stable-image-ultra', 'stable-image-core', 'stable-image-sd3', 'stable-audio-2']:
            return self._get_stability_response(model, messages, max_tokens, temperature)
        else:
            raise ValueError(f"Model {model} not available")
    
    def _get_openai_response(self, model, messages, max_tokens, temperature, is_authenticated=False):
        """Get response from OpenAI models using v1.x client"""
        if not self.openai_available or not self.openai_client:
            raise Exception("OpenAI API key not configured")
            
        try:
            # Calculate rough token count to prevent silent failures
            total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
            estimated_tokens = total_chars // 3  # Rough estimate: 3 chars per token
            
            self.logger.info(f"OpenAI request: model={model}, estimated_tokens={estimated_tokens}, max_tokens={max_tokens}, authenticated={is_authenticated}")
            
            # Check if we're likely to exceed limits (only for free users)
            if not is_authenticated:
                model_limits = self.get_model_limits(model)
                if estimated_tokens + max_tokens > model_limits['context_window']:
                    raise Exception(f"Request too large for {model}. Estimated {estimated_tokens} tokens, max allowed {model_limits['context_window']}. Try using Gemini Pro or Claude for large documents.")
            else:
                self.logger.info("Skipping token limits for authenticated user")
            
            # O1 models have different API requirements
            if model.startswith('o1'):
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_completion_tokens=max_tokens
                    # O1 models don't support temperature parameter
                )
            else:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            
            text = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            # Updated pricing (as of 2024):
            # gpt-4: $0.03/1K prompt, $0.06/1K completion; gpt-3.5: $0.001/1K; o1: $15/1M
            if model.startswith('o1-preview'):
                cost = tokens * 0.000015  # $15/1M tokens
            elif model.startswith('o1-mini'):
                cost = tokens * 0.000003  # $3/1M tokens  
            elif model.startswith('gpt-4'):
                cost = tokens * 0.00006  # $0.06/1K tokens (rough estimate)
            elif model.startswith('gpt-3.5'):
                cost = tokens * 0.000002  # $0.002/1K tokens
            else:
                cost = tokens * 0.00002  # fallback
            return text, tokens, cost
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {type(e).__name__}: {str(e)}")
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

    def _get_stability_response(self, model, messages, max_tokens, temperature):
        """Get response from Stability AI models (Image/Audio generation)"""
        if not self.stability_available:
            raise Exception("Stability AI API key not configured")
            
        try:
            # Get the latest user message as the prompt
            user_message = None
            for msg in reversed(messages):
                if msg['role'] == 'user':
                    user_message = msg['content']
                    break
            
            if not user_message:
                raise Exception("No user prompt found for Stability AI generation")
            
            # Map model names to endpoints and handle different generation types
            if model == 'stable-image-ultra':
                endpoint = "https://api.stability.ai/v2beta/stable-image/generate/ultra"
                return self._generate_image(endpoint, user_message, "ultra")
            
            elif model == 'stable-image-core':
                endpoint = "https://api.stability.ai/v2beta/stable-image/generate/core"
                return self._generate_image(endpoint, user_message, "core")
            
            elif model == 'stable-image-sd3':
                endpoint = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
                return self._generate_image(endpoint, user_message, "sd3")
            
            elif model == 'stable-audio-2':
                endpoint = "https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio"
                return self._generate_audio(endpoint, user_message)
            
            else:
                raise Exception(f"Unknown Stability AI model: {model}")
                
        except Exception as e:
            raise Exception(f"Stability AI API error: {str(e)}")
    
    def _generate_image(self, endpoint, prompt, model_type):
        """Generate image using Stability AI v2beta endpoints"""
        try:
            # Prepare form data for image generation
            files = {
                'prompt': (None, prompt),
                'output_format': (None, 'png'),
            }
            
            # Add model-specific parameters
            if model_type == "ultra":
                files['aspect_ratio'] = (None, '1:1')
            elif model_type == "core":
                files['style_preset'] = (None, 'photographic')
                files['aspect_ratio'] = (None, '1:1')
            elif model_type == "sd3":
                files['aspect_ratio'] = (None, '1:1')
                files['seed'] = (None, '0')
            
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.stability_api_key}",
                    "Accept": "image/*"
                },
                files=files,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Stability API returned {response.status_code}: {response.text}")
            
            # Upload image to Cloudinary instead of local storage
            import base64
            import os
            from datetime import datetime
            import cloudinary
            import cloudinary.uploader
            
            # Configure Cloudinary (if not already configured)
            cloudinary.config(
                cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                api_key=os.getenv('CLOUDINARY_API_KEY'),
                api_secret=os.getenv('CLOUDINARY_API_SECRET'),
                secure=True
            )
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stability_{model_type}_{timestamp}"
            
            try:
                # Upload image to Cloudinary from binary data
                upload_result = cloudinary.uploader.upload(
                    response.content,
                    public_id=filename,
                    folder="ai-generated",
                    resource_type="image",
                    format="png"
                )
                
                # Get the secure URL from Cloudinary
                web_path = upload_result['secure_url']
                filename_with_ext = f"{filename}.png"
                
            except Exception as cloudinary_error:
                # Fallback to local storage if Cloudinary fails
                self.logger.warning(f"Cloudinary upload failed: {cloudinary_error}. Falling back to local storage.")
                
                # Create images directory if it doesn't exist
                images_dir = os.path.join(os.path.dirname(__file__), 'static', 'generated_images')
                os.makedirs(images_dir, exist_ok=True)
                
                filename_with_ext = f"{filename}.png"
                file_path = os.path.join(images_dir, filename_with_ext)
                
                # Save the image locally
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                # Create relative path for web access
                web_path = f"/static/generated_images/{filename_with_ext}"
            
            # Return response with image
            text_response = f"✅ **Image Generated Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model_type.title()}\n"
            text_response += f"**Prompt:** {prompt}\n"
            text_response += f"**Format:** PNG image\n"
            text_response += f"**Status:** Image generated and ready\n\n"
            text_response += f"![Generated Image]({web_path})\n\n"
            text_response += f"**Image saved as:** {filename_with_ext}"
            
            # Estimate tokens and cost
            tokens = len(prompt.split()) + 50  # Prompt tokens + generation overhead
            cost = 0.05  # Rough cost for image generation
            
            return text_response, tokens, cost
                
        except Exception as e:
            raise Exception(f"Image generation error: {str(e)}")
    
    def _generate_audio(self, endpoint, prompt):
        """Generate audio using Stability AI v2beta endpoints"""
        try:
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.stability_api_key}",
                    "Content-Type": "application/json",
                    "Accept": "audio/*"
                },
                json={
                    "prompt": prompt,
                    "length": 10.0,  # 10 second audio clip
                    "output_format": "mp3"
                },
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Stability API returned {response.status_code}: {response.text}")
            
            # For successful audio generation, return a description
            text_response = f"🎵 **Audio Generated Successfully**\n\n"
            text_response += f"**Model:** Stability AI Audio 2\n"
            text_response += f"**Prompt:** {prompt}\n"
            text_response += f"**Duration:** 10 seconds\n"
            text_response += f"**Format:** MP3 audio\n"
            text_response += f"**Status:** Audio generated and ready\n\n"
            text_response += "*Note: This is an audio generation model. The actual audio file would be playable in a full implementation.*"
            
            # Estimate tokens and cost
            tokens = len(prompt.split()) + 30  # Prompt tokens + generation overhead
            cost = 0.03  # Rough cost for audio generation
            
            return text_response, tokens, cost
                
        except Exception as e:
            raise Exception(f"Audio generation error: {str(e)}")
    
    def get_model_limits(self, model):
        """Get practical token limits for different models"""
        limits = {
            # OpenAI Models - Updated to current limits (2024)
            'gpt-4': {'max_tokens': 4000, 'context_window': 8000},
            'gpt-4-turbo': {'max_tokens': 4000, 'context_window': 128000},
            'gpt-4o': {'max_tokens': 4000, 'context_window': 128000},
            'gpt-4o-mini': {'max_tokens': 4000, 'context_window': 128000},
            'gpt-3.5-turbo': {'max_tokens': 4000, 'context_window': 16000},
            'o1-preview': {'max_tokens': 32768, 'context_window': 128000},
            'o1-mini': {'max_tokens': 65536, 'context_window': 128000},
            
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
            'codellama-34b': {'max_tokens': 3000, 'context_window': 14000},
            
            # Stability AI Models (Image & Audio Generation)
            'stable-image-ultra': {'max_tokens': 500, 'context_window': 1000},
            'stable-image-core': {'max_tokens': 500, 'context_window': 1000},
            'stable-image-sd3': {'max_tokens': 500, 'context_window': 1000},
            'stable-audio-2': {'max_tokens': 300, 'context_window': 600}
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