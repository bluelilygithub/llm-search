// Test file to verify modules are working
console.log('Testing modular structure...');

// Test Utils
if (window.Utils) {
    console.log('✅ Utils module loaded successfully');
    console.log('Utils methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(window.Utils)));
} else {
    console.error('❌ Utils module not loaded');
}

// Test ChatManager
if (window.ChatManager) {
    console.log('✅ ChatManager module loaded successfully');
    console.log('ChatManager methods:', Object.getOwnPropertyNames(window.ChatManager.prototype));
} else {
    console.error('❌ ChatManager module not loaded');
}

// Test ProjectManager
if (window.ProjectManager) {
    console.log('✅ ProjectManager module loaded successfully');
    console.log('ProjectManager methods:', Object.getOwnPropertyNames(window.ProjectManager.prototype));
} else {
    console.error('❌ ProjectManager module not loaded');
}

console.log('Module test complete');
