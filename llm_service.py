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
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stability_{model_type}_{timestamp}"
            
            try:
                # Configure Cloudinary right before upload
                cloudinary.config(
                    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                    api_key=os.getenv('CLOUDINARY_API_KEY'),
                    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
                    secure=True
                )
                
                # Upload image to Cloudinary from binary data using BytesIO
                from io import BytesIO
                image_buffer = BytesIO(response.content)
                
                upload_result = cloudinary.uploader.upload(
                    image_buffer,
                    public_id=filename,
                    folder="ai-generated",
                    resource_type="image"
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
    
    def edit_image(self, image_file, model, prompt):
        """Edit an uploaded image using Stability AI image editing APIs"""
        if not self.stability_available:
            raise Exception("Stability AI API key not configured")
        
        try:
            # Determine the editing operation based on the prompt
            editing_operation = self._detect_editing_operation(prompt)
            
            if editing_operation == "background":
                return self._edit_background(image_file, prompt, model)
            elif editing_operation == "erase":
                return self._erase_objects(image_file, prompt, model)
            elif editing_operation == "inpaint":
                return self._inpaint_image(image_file, prompt, model)
            elif editing_operation == "outpaint":
                return self._outpaint_image(image_file, prompt, model)
            elif editing_operation == "search_replace":
                return self._search_and_replace(image_file, prompt, model)
            elif editing_operation == "search_recolor":
                return self._search_and_recolor(image_file, prompt, model)
            else:
                # Default to general editing
                return self._general_image_edit(image_file, prompt, model)
                
        except Exception as e:
            raise Exception(f"Image editing error: {str(e)}")
    
    def _detect_editing_operation(self, prompt):
        """Detect what type of editing operation is requested"""
        prompt_lower = prompt.lower()
        
        # Background operations
        if any(word in prompt_lower for word in ["background", "backdrop", "bg"]):
            return "background"
        
        # Erasing operations
        elif any(word in prompt_lower for word in ["erase", "remove", "delete", "eliminate"]):
            return "erase"
        
        # Extending operations
        elif any(word in prompt_lower for word in ["extend", "expand", "outpaint", "continue"]):
            return "outpaint"
        
        # Recoloring operations
        elif any(word in prompt_lower for word in ["recolor", "change color", "color to"]):
            return "search_recolor"
        
        # Search and replace operations
        elif any(word in prompt_lower for word in ["replace", "change to", "turn into"]):
            return "search_replace"
        
        # Inpainting operations
        elif any(word in prompt_lower for word in ["fill", "inpaint", "complete", "fix"]):
            return "inpaint"
        
        else:
            return "general"
    
    def _edit_background(self, image_file, prompt, model):
        """Handle background removal/replacement operations"""
        try:
            # Check if it's background removal or replacement
            if any(word in prompt.lower() for word in ["remove background", "no background", "transparent"]):
                endpoint = "https://api.stability.ai/v2beta/stable-image/edit/remove-background"
                return self._remove_background(image_file, endpoint, model)
            else:
                # Background replacement/modification
                endpoint = "https://api.stability.ai/v2beta/stable-image/edit/search-and-replace"
                return self._replace_background_api(image_file, prompt, endpoint, model)
                
        except Exception as e:
            raise Exception(f"Background editing error: {str(e)}")
    
    def _remove_background(self, image_file, endpoint, model):
        """Remove background from image"""
        try:
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type)
            }
            
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
                raise Exception(f"Background removal failed: {response.status_code} - {response.text}")
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "bg_removed", model)
            
            # Return response with edited image
            text_response = f"✅ **Background Removed Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Background Removal\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = 50  # Fixed for background removal
            cost = 0.04  # Cost for background removal
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Background removal error: {str(e)}")
    
    def _replace_background_api(self, image_file, prompt, endpoint, model):
        """Replace/modify background using search and replace"""
        try:
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type),
                'prompt': (None, prompt),
                'search_prompt': (None, 'background'),
                'output_format': (None, 'png')
            }
            
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
                raise Exception(f"Background replacement failed: {response.status_code} - {response.text}")
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "bg_replaced", model)
            
            text_response = f"✅ **Background Modified Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Background Replacement\n"
            text_response += f"**Prompt:** {prompt}\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = len(prompt.split()) + 30
            cost = 0.05  # Cost for background replacement
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Background replacement error: {str(e)}")
    
    def _erase_objects(self, image_file, prompt, model):
        """Erase objects from image using inpainting"""
        try:
            # Use erase endpoint if available, otherwise fall back to inpainting
            endpoint = "https://api.stability.ai/v2beta/stable-image/edit/erase"
            
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type),
                'prompt': (None, prompt),
                'output_format': (None, 'png')
            }
            
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
                # Fallback to search and replace with empty replacement
                return self._search_and_replace(image_file, f"remove {prompt}", model)
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "erased", model)
            
            text_response = f"✅ **Objects Erased Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Object Removal\n"
            text_response += f"**Target:** {prompt}\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = len(prompt.split()) + 25
            cost = 0.04
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Object erasing error: {str(e)}")
    
    def _search_and_replace(self, image_file, prompt, model):
        """Search and replace objects in image"""
        try:
            endpoint = "https://api.stability.ai/v2beta/stable-image/edit/search-and-replace"
            
            # Extract search and replace terms from prompt
            search_term, replace_term = self._parse_search_replace_prompt(prompt)
            
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type),
                'prompt': (None, replace_term),
                'search_prompt': (None, search_term),
                'output_format': (None, 'png')
            }
            
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
                raise Exception(f"Search and replace failed: {response.status_code} - {response.text}")
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "replaced", model)
            
            text_response = f"✅ **Object Replaced Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Search & Replace\n"
            text_response += f"**Search:** {search_term}\n"
            text_response += f"**Replace:** {replace_term}\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = len(prompt.split()) + 30
            cost = 0.05
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Search and replace error: {str(e)}")
    
    def _search_and_recolor(self, image_file, prompt, model):
        """Change colors of specific objects"""
        try:
            endpoint = "https://api.stability.ai/v2beta/stable-image/edit/search-and-recolor"
            
            # Extract object and color from prompt
            search_term, color = self._parse_recolor_prompt(prompt)
            
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type),
                'prompt': (None, color),
                'select_prompt': (None, search_term),
                'output_format': (None, 'png')
            }
            
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
                raise Exception(f"Recoloring failed: {response.status_code} - {response.text}")
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "recolored", model)
            
            text_response = f"✅ **Object Recolored Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Search & Recolor\n"
            text_response += f"**Object:** {search_term}\n"
            text_response += f"**New Color:** {color}\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = len(prompt.split()) + 25
            cost = 0.04
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Recoloring error: {str(e)}")
    
    def _outpaint_image(self, image_file, prompt, model):
        """Extend image boundaries using outpainting"""
        try:
            endpoint = "https://api.stability.ai/v2beta/stable-image/edit/outpaint"
            
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type),
                'prompt': (None, prompt),
                'left': (None, '0'),
                'right': (None, '512'),
                'up': (None, '0'),  
                'down': (None, '0'),
                'output_format': (None, 'png')
            }
            
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
                raise Exception(f"Outpainting failed: {response.status_code} - {response.text}")
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "outpainted", model)
            
            text_response = f"✅ **Image Extended Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Outpainting\n"
            text_response += f"**Prompt:** {prompt}\n"
            text_response += f"**Extension:** Right side expanded\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = len(prompt.split()) + 35
            cost = 0.06
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Outpainting error: {str(e)}")
    
    def _inpaint_image(self, image_file, prompt, model):
        """Fill in missing areas using inpainting"""
        try:
            endpoint = "https://api.stability.ai/v2beta/stable-image/edit/inpaint"
            
            # Reset file pointer to beginning
            image_file.seek(0)
            
            files = {
                'image': (image_file.filename, image_file.read(), image_file.content_type),
                'prompt': (None, prompt),
                'output_format': (None, 'png')
            }
            
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
                raise Exception(f"Inpainting failed: {response.status_code} - {response.text}")
            
            # Upload result to Cloudinary
            web_path, filename = self._upload_edited_image(response.content, "inpainted", model)
            
            text_response = f"✅ **Image Inpainted Successfully**\n\n"
            text_response += f"**Model:** Stability AI {model}\n"
            text_response += f"**Operation:** Inpainting\n"
            text_response += f"**Prompt:** {prompt}\n"
            text_response += f"**Status:** Image processed and ready\n\n"
            text_response += f"![Edited Image]({web_path})\n\n"
            text_response += f"**Saved as:** {filename}"
            
            tokens = len(prompt.split()) + 30
            cost = 0.05
            
            return text_response, tokens, cost
            
        except Exception as e:
            raise Exception(f"Inpainting error: {str(e)}")
    
    def _general_image_edit(self, image_file, prompt, model):
        """General image editing using search and replace as fallback"""
        try:
            # Use search and replace with the full prompt
            return self._search_and_replace(image_file, prompt, model)
            
        except Exception as e:
            raise Exception(f"General image editing error: {str(e)}")
    
    def _upload_edited_image(self, image_data, operation_type, model):
        """Upload edited image to Cloudinary or save locally"""
        import base64
        import os
        from datetime import datetime
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stability_{operation_type}_{timestamp}.png"
        
        try:
            import cloudinary
            import cloudinary.uploader
            from io import BytesIO
            
            # Configure Cloudinary
            cloudinary.config(
                cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
                api_key=os.getenv('CLOUDINARY_API_KEY'),
                api_secret=os.getenv('CLOUDINARY_API_SECRET'),
                secure=True
            )
            
            # Upload to Cloudinary from binary data
            image_buffer = BytesIO(image_data)
            
            upload_result = cloudinary.uploader.upload(
                image_buffer,
                public_id=f"ai-edited/{filename.replace('.png', '')}",
                folder="ai-edited",
                resource_type="image"
            )
            
            return upload_result['secure_url'], filename
            
        except Exception as cloudinary_error:
            # Fallback to local storage
            self.logger.warning(f"Cloudinary upload failed: {cloudinary_error}. Falling back to local storage.")
            
            images_dir = os.path.join(os.path.dirname(__file__), 'static', 'generated_images')
            os.makedirs(images_dir, exist_ok=True)
            
            file_path = os.path.join(images_dir, filename)
            
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            web_path = f"/static/generated_images/{filename}"
            return web_path, filename
    
    def _parse_search_replace_prompt(self, prompt):
        """Parse search and replace terms from prompt"""
        prompt_lower = prompt.lower()
        
        # Common patterns for search and replace
        if "replace" in prompt_lower and "with" in prompt_lower:
            parts = prompt.split(" with ")
            if len(parts) == 2:
                search_term = parts[0].replace("replace ", "").strip()
                replace_term = parts[1].strip()
                return search_term, replace_term
        
        elif "change" in prompt_lower and "to" in prompt_lower:
            parts = prompt.split(" to ")
            if len(parts) == 2:
                search_term = parts[0].replace("change ", "").strip()
                replace_term = parts[1].strip()
                return search_term, replace_term
        
        # Default fallback
        return "object", prompt
    
    def _parse_recolor_prompt(self, prompt):
        """Parse object and color from recoloring prompt"""
        prompt_lower = prompt.lower()
        
        # Extract color words
        colors = ["red", "blue", "green", "yellow", "orange", "purple", "pink", "brown", "black", "white", "gray", "grey"]
        found_color = "blue"  # default
        
        for color in colors:
            if color in prompt_lower:
                found_color = color
                break
        
        # Extract object (everything before color-related words)
        color_words = ["color", "to", found_color]
        object_part = prompt_lower
        for word in color_words:
            if word in object_part:
                object_part = object_part.split(word)[0]
        
        search_term = object_part.replace("change", "").replace("recolor", "").strip()
        if not search_term:
            search_term = "object"
        
        return search_term, found_color
    
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