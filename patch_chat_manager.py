with open('static/js/modules/chat-manager.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the askFollowUpQuestion method and replace it
old_method = """    askFollowUpQuestion(question) {
        const messageInput = this.uiController.getElement('message-input');
        if (messageInput) {
            messageInput.value = question;
            this.sendMessage();
        }
    }"""

new_method = """    askFollowUpQuestion(question) {
        console.log('Follow-up question:', question);
        
        // Check if this is a diagram request
        if (question.toLowerCase().includes('illustrate') || 
            question.toLowerCase().includes('diagram') || 
            question.toLowerCase().includes('graphic')) {
            console.log('Detected diagram request');
            this.generateAndDisplayDiagram();
            return;
        }
        
        const messageInput = this.uiController.getElement('message-input');
        if (messageInput) {
            messageInput.value = question;
            this.sendMessage();
        }
    }

    /**
     * Generate and display a diagram for math problems
     */
    async generateAndDisplayDiagram() {
        try {
            console.log('Starting diagram generation');
            const chatArea = this.uiController.getElement('chat-messages');
            if (!chatArea) {
                alert('Chat area not found');
                return;
            }
            
            const messages = chatArea.querySelectorAll('.message');
            if (messages.length === 0) {
                alert('No AI response found');
                return;
            }
            
            const lastMessage = messages[messages.length - 1];
            const responseText = lastMessage.querySelector('.message-content')?.textContent || '';
            
            if (!responseText) {
                alert('Could not extract response');
                return;
            }
            
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'diagram-loading';
            loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating diagram...';
            chatArea.appendChild(loadingDiv);
            
            const response = await fetch('/api/generate-diagram', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    response: responseText,
                    problem: this.lastUserMessage || '',
                    model: 'stable-image-ultra'
                })
            });
            
            loadingDiv.remove();
            
            if (response.ok) {
                const data = await response.json();
                const diagramDiv = document.createElement('div');
                diagramDiv.className = 'generated-diagram';
                diagramDiv.innerHTML = `
                    <div class="diagram-container">
                        <div class="diagram-title">
                            <i class="fas fa-image"></i>
                            Professional Diagram
                        </div>
                        <img src="${data.image_url}" alt="Generated diagram" class="diagram-image" />
                        <div class="diagram-info">
                            <small>Generated with Stability AI</small>
                        </div>
                    </div>
                `;
                chatArea.appendChild(diagramDiv);
                chatArea.scrollTop = chatArea.scrollHeight;
            } else {
                const error = await response.json();
                alert('Failed to generate diagram: ' + (error.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Diagram error:', error);
            alert('Error: ' + error.message);
        }
    }"""

if old_method in content:
    content = content.replace(old_method, new_method)
    with open('static/js/modules/chat-manager.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated successfully")
else:
    print("Method not found")
