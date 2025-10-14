# Template System Debugging Guide

## Status: ✅ System Implemented

Your template system **is implemented** and should be working. Here's how to verify and debug:

---

## 🔍 Quick Verification Steps

### 1. Check Console Logs on Page Load

When you load the page, you should see these console messages:
```
📝 Template & Prompt Library: LOADED
📋 Available templates: 6
📋 Template IDs: ['email-template', 'code-review', 'meeting-notes', 'brainstorming', 'research', 'blog-post']
✅ Template modal found in DOM
🔘 Template buttons found: 2
   Button 1: template-btn Templates
   Button 2: input-control-btn 
💡 Debug tip: Type testTemplateModal() in console to test the template system
```

### 2. Locate the Template Buttons

There are **2 buttons** that open the template picker:

**Button 1: Top Bar (Red Button)**
- Located next to the model selector dropdown
- Red background (#ff6b6b)
- Has an icon and text "Templates"

**Button 2: Input Controls (Icon Only)**
- Located in the message input area
- Icon button with file-alt icon
- Next to the microphone button

### 3. Test the Modal Manually

Open Chrome DevTools Console and run:
```javascript
testTemplateModal()
```

This will:
- Check if window.app exists
- Verify the modal element is in the DOM
- Show current display styles and z-index
- Attempt to open the modal automatically

### 4. Manual Modal Test

If the buttons don't work, try this in the console:
```javascript
// Force open the modal
document.getElementById('template-modal').style.display = 'flex';
```

To close it:
```javascript
document.getElementById('template-modal').style.display = 'none';
```

---

## 🐛 Common Issues & Solutions

### Issue 1: Buttons Not Visible

**Check:**
```javascript
document.querySelectorAll('[onclick*="openTemplatePicker"]')
```

**Solution:** If buttons don't exist, refresh the page or check if you're on the correct page (index.html vs other templates).

### Issue 2: Modal Opens But Nothing Inside

**Check:**
```javascript
document.querySelectorAll('.template-card').length
```

Should return `6` (the 6 hardcoded template cards).

**Solution:** The template cards are hardcoded in `templates/index.html`. Make sure you're using the correct template file.

### Issue 3: Modal Opens Behind Other Elements

**Check:**
```javascript
window.getComputedStyle(document.getElementById('template-modal')).zIndex
```

Should return `10000`.

**Solution:** Already fixed in the CSS update. Z-index increased from 1000 to 10000.

### Issue 4: Click Does Nothing

**Check:**
```javascript
window.app.openTemplatePicker
```

Should return a function, not undefined.

**Solution:** Make sure the page fully loaded and window.app is initialized. Wait for DOM ready.

---

## 📊 What Gets Logged When You Click

When you click a template button, you should see:
```
✅ Template Picker Opening!
🔍 Checking for modal element...
📦 Modal element: [object HTMLDivElement]
✅ Modal found! Current display: none
✅ Modal display set to flex. New value: flex
📏 Modal computed style: flex
✅ Search input focused
```

When you select a template, you should see:
```
📝 Selecting template: email-template
✅ Template found: {name: 'Email Template', content: '...', ...}
✅ Model set to: claude-3.5-sonnet
✅ Template content applied to message input
```

---

## ✅ Expected Behavior

1. **Click template button** → Modal opens with semi-transparent black backdrop
2. **See 6 template cards** → Each with icon, title, description, and model name
3. **Search bar at top** → Can filter templates by name
4. **Category tabs** → All, Writing, Research, Code, Creative
5. **Click a template card** → Modal closes, template content appears in message input, recommended model is auto-selected
6. **Cancel button** → Closes modal without applying template

---

## 🧪 Advanced Debugging

### Inspect All Template Elements

```javascript
console.log('Modal:', document.getElementById('template-modal'));
console.log('Modal Content:', document.getElementById('template-grid'));
console.log('Template Cards:', document.querySelectorAll('.template-card').length);
console.log('Category Tabs:', document.querySelectorAll('.category-tab').length);
console.log('Template Data:', TEMPLATE_DATA);
console.log('App Instance:', window.app);
console.log('Open Function:', window.app.openTemplatePicker);
```

### Force Open and Test Each Template

```javascript
// Open modal
window.app.openTemplatePicker();

// Test selecting each template
['email-template', 'code-review', 'meeting-notes', 'brainstorming', 'research', 'blog-post']
  .forEach(id => {
    console.log(`Testing: ${id}`);
    window.app.selectTemplate(id);
  });
```

---

## 📝 Files Modified

1. **static/js/app.js**
   - Added enhanced logging to `openTemplatePicker()`
   - Added enhanced logging to `selectTemplate()`
   - Added `testTemplateModal()` global function
   - Added initialization checks on DOM load

2. **static/css/style.css**
   - Increased `.template-modal` z-index from 1000 to 10000

---

## 🎯 Next Steps

1. ✅ Open your Railway app in browser
2. ✅ Open Chrome DevTools (F12)
3. ✅ Go to Console tab
4. ✅ Look for the template loading messages
5. ✅ Look for the red "Templates" button in the top bar
6. ✅ Click it and verify the modal opens
7. ✅ Try clicking a template card
8. ✅ Verify the template content appears in the message input

If you see any errors, copy them and I'll help you fix them!

---

## 💡 Pro Tip

Once working, you can:
- Add more templates to `TEMPLATE_DATA` in app.js
- Customize template content and placeholders
- Change default models for each template
- Add more categories
- Implement the "Create Custom Template" feature (currently shows "coming soon")

