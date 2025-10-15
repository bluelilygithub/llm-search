#!/usr/bin/env python3
"""
Template Migration Script

This script migrates the hardcoded templates from JavaScript to the database.
Run this after the Template table has been created.
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Template

def migrate_templates():
    """Migrate hardcoded templates to database"""
    
    # Hardcoded templates from JavaScript (with enhanced data)
    templates_data = [
        {
            'name': 'Email Template',
            'content': 'Please help me write a professional email about {{topic}}. The email should be {{tone}} and include {{details}}.',
            'category': 'writing',
            'default_model': 'claude-3.5-sonnet',
            'icon': 'fas fa-envelope',
            'description': 'Professional email writing',
            'usage_count': 245,
            'is_public': True
        },
        {
            'name': 'Code Review',
            'content': 'Please review this code for best practices, potential bugs, and improvements:\n\n```\n{{code}}\n```\n\nFocus on: {{focus_areas}}',
            'category': 'code',
            'default_model': 'gpt-4',
            'icon': 'fas fa-code',
            'description': 'Comprehensive code analysis',
            'usage_count': 189,
            'is_public': True
        },
        {
            'name': 'Meeting Notes',
            'content': 'Please help me organize these meeting notes into a structured format:\n\n{{notes}}\n\nInclude: agenda, key decisions, action items, and next steps.',
            'category': 'writing',
            'default_model': 'claude-3.5-sonnet',
            'icon': 'fas fa-clipboard',
            'description': 'Structured meeting documentation',
            'usage_count': 156,
            'is_public': True
        },
        {
            'name': 'Brainstorming',
            'content': 'Help me brainstorm creative ideas for {{topic}}. Consider these constraints: {{constraints}}. Generate {{number}} innovative solutions.',
            'category': 'creative',
            'default_model': 'claude-3.5-sonnet',
            'icon': 'fas fa-lightbulb',
            'description': 'Creative idea generation',
            'usage_count': 134,
            'is_public': True
        },
        {
            'name': 'Research',
            'content': 'Help me research {{topic}}. Please provide:\n1. Key facts and statistics\n2. Current trends\n3. Expert opinions\n4. Potential challenges\n5. Future outlook',
            'category': 'research',
            'default_model': 'gpt-4',
            'icon': 'fas fa-search',
            'description': 'Academic research assistance',
            'usage_count': 98,
            'is_public': True
        },
        {
            'name': 'Blog Post',
            'content': 'Help me write an engaging blog post about {{topic}}. Target audience: {{audience}}. Tone: {{tone}}. Length: {{length}} words.',
            'category': 'writing',
            'default_model': 'claude-3.5-sonnet',
            'icon': 'fas fa-blog',
            'description': 'Engaging blog content',
            'usage_count': 87,
            'is_public': True
        }
    ]
    
    with app.app_context():
        try:
            # Check if templates already exist
            existing_count = Template.query.count()
            if existing_count > 0:
                print(f"⚠️  Found {existing_count} existing templates in database.")
                response = input("Do you want to continue? This will add new templates (y/N): ")
                if response.lower() != 'y':
                    print("❌ Migration cancelled.")
                    return
            
            # Use a system user ID for default templates
            system_user_id = 'system_default'
            
            created_count = 0
            for template_data in templates_data:
                # Check if template already exists by name
                existing = Template.query.filter_by(
                    name=template_data['name'],
                    user_id=system_user_id
                ).first()
                
                if existing:
                    print(f"⏭️  Skipping existing template: {template_data['name']}")
                    continue
                
                # Create new template
                template = Template(
                    user_id=system_user_id,
                    name=template_data['name'],
                    content=template_data['content'],
                    category=template_data['category'],
                    default_model=template_data['default_model'],
                    description=template_data['description'],
                    icon=template_data['icon'],
                    usage_count=template_data['usage_count'],
                    is_public=template_data['is_public'],
                    is_active=True
                )
                
                db.session.add(template)
                created_count += 1
                print(f"✅ Created template: {template_data['name']}")
            
            if created_count > 0:
                db.session.commit()
                print(f"\n🎉 Successfully migrated {created_count} templates to database!")
                print(f"📊 Total templates in database: {Template.query.count()}")
            else:
                print("\n✅ All templates already exist in database.")
            
            # Show summary
            print("\n📋 Template Summary:")
            for template in Template.query.filter_by(is_active=True).all():
                print(f"  • {template.name} ({template.category}) - {template.usage_count} uses")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error migrating templates: {str(e)}")
            raise

if __name__ == '__main__':
    print("🚀 Starting Template Migration...")
    migrate_templates()
    print("✨ Migration completed!")
