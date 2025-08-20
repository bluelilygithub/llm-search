from database import db
from models import ContextItem, ContextSession, ContextUsageLog, ContextTemplate
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import uuid
import hashlib


class ContextService:
    """Core business logic for context management"""
    
    @staticmethod
    def get_user_id():
        """Get user identifier (session-based for now, can be enhanced later)"""
        from flask import session
        if 'user_id' not in session:
            session['user_id'] = str(uuid.uuid4())
        return session['user_id']
    
    @staticmethod
    def create_context_item(
        name: str,
        content_type: str,
        content_text: str = None,
        description: str = None,
        original_filename: str = None,
        file_path: str = None,
        file_size: int = None,
        extra_data: Dict[str, Any] = None
    ) -> ContextItem:
        """Create a new context item"""
        
        user_id = ContextService.get_user_id()
        
        # Estimate token count (rough approximation)
        token_count = 0
        if content_text:
            token_count = len(content_text.split()) * 1.3  # Rough token estimation
        
        context_item = ContextItem(
            user_id=user_id,
            name=name,
            description=description,
            content_type=content_type,
            content_text=content_text,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            token_count=int(token_count),
            extra_data=extra_data or {}
        )
        
        db.session.add(context_item)
        db.session.commit()
        
        return context_item
    
    @staticmethod
    def get_user_context_items(include_inactive: bool = False) -> List[ContextItem]:
        """Get all context items for current user"""
        
        user_id = ContextService.get_user_id()
        
        query = ContextItem.query.filter_by(user_id=user_id)
        
        if not include_inactive:
            query = query.filter_by(is_active=True)
            
        return query.order_by(ContextItem.last_used_at.desc().nullsfirst(), 
                            ContextItem.created_at.desc()).all()
    
    @staticmethod
    def get_context_item(item_id: str) -> Optional[ContextItem]:
        """Get a specific context item by ID"""
        
        user_id = ContextService.get_user_id()
        
        return ContextItem.query.filter_by(
            id=item_id, 
            user_id=user_id,
            is_active=True
        ).first()
    
    @staticmethod
    def update_context_item(
        item_id: str,
        name: str = None,
        description: str = None,
        content_text: str = None,
        extra_data: Dict[str, Any] = None
    ) -> Optional[ContextItem]:
        """Update an existing context item"""
        
        context_item = ContextService.get_context_item(item_id)
        if not context_item:
            return None
        
        if name is not None:
            context_item.name = name
        if description is not None:
            context_item.description = description
        if content_text is not None:
            context_item.content_text = content_text
            # Update token count
            context_item.token_count = int(len(content_text.split()) * 1.3)
        if extra_data is not None:
            context_item.extra_data = extra_data
            
        context_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        return context_item
    
    @staticmethod
    def delete_context_item(item_id: str) -> bool:
        """Soft delete a context item"""
        
        context_item = ContextService.get_context_item(item_id)
        if not context_item:
            return False
        
        context_item.is_active = False
        context_item.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
    
    @staticmethod
    def add_context_to_conversation(conversation_id: str, context_item_id: str, relevance_score: float = 1.0) -> Optional[ContextSession]:
        """Add context item to a conversation"""
        
        # Check if context item exists and belongs to user
        context_item = ContextService.get_context_item(context_item_id)
        if not context_item:
            return None
        
        # Check if already added to this conversation
        existing = ContextSession.query.filter_by(
            conversation_id=conversation_id,
            context_item_id=context_item_id,
            is_active=True
        ).first()
        
        if existing:
            # Update relevance score and access time
            existing.relevance_score = relevance_score
            existing.last_accessed_at = datetime.utcnow()
            db.session.commit()
            return existing
        
        # Create new context session
        context_session = ContextSession(
            conversation_id=conversation_id,
            context_item_id=context_item_id,
            relevance_score=relevance_score
        )
        
        db.session.add(context_session)
        
        # Update context item usage
        context_item.usage_count += 1
        context_item.last_used_at = datetime.utcnow()
        
        db.session.commit()
        return context_session
    
    @staticmethod
    def remove_context_from_conversation(conversation_id: str, context_item_id: str) -> bool:
        """Remove context item from a conversation"""
        
        context_session = ContextSession.query.filter_by(
            conversation_id=conversation_id,
            context_item_id=context_item_id,
            is_active=True
        ).first()
        
        if not context_session:
            return False
        
        context_session.is_active = False
        db.session.commit()
        return True
    
    @staticmethod
    def get_conversation_context(conversation_id: str) -> List[Dict[str, Any]]:
        """Get all active context for a conversation"""
        
        context_sessions = db.session.query(ContextSession, ContextItem).join(
            ContextItem, ContextSession.context_item_id == ContextItem.id
        ).filter(
            ContextSession.conversation_id == conversation_id,
            ContextSession.is_active == True,
            ContextItem.is_active == True
        ).order_by(ContextSession.relevance_score.desc()).all()
        
        result = []
        for session, item in context_sessions:
            result.append({
                'session_id': str(session.id),
                'item_id': str(item.id),
                'name': item.name,
                'description': item.description,
                'content_type': item.content_type,
                'content_text': item.content_text,
                'content_summary': item.content_summary,
                'token_count': item.token_count,
                'relevance_score': float(session.relevance_score),
                'added_at': session.added_at.isoformat(),
                'last_accessed_at': session.last_accessed_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def log_context_usage(
        conversation_id: str,
        message_id: str,
        context_item_id: str,
        usage_type: str = 'input',
        influence_score: float = 0.0,
        tokens_consumed: int = 0
    ) -> ContextUsageLog:
        """Log context usage for analytics"""
        
        usage_log = ContextUsageLog(
            conversation_id=conversation_id,
            message_id=message_id,
            context_item_id=context_item_id,
            usage_type=usage_type,
            influence_score=influence_score,
            tokens_consumed=tokens_consumed
        )
        
        db.session.add(usage_log)
        db.session.commit()
        
        return usage_log
    
    @staticmethod
    def get_context_suggestions(query_text: str, conversation_id: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get context suggestions based on query text (basic implementation)"""
        
        user_id = ContextService.get_user_id()
        
        # Simple keyword-based matching (can be enhanced with semantic search later)
        query_words = query_text.lower().split()
        
        all_items = ContextItem.query.filter_by(user_id=user_id, is_active=True).all()
        
        suggestions = []
        for item in all_items:
            score = 0.0
            searchable_text = f"{item.name} {item.description or ''} {item.content_text or ''}".lower()
            
            # Simple keyword matching
            for word in query_words:
                if word in searchable_text:
                    score += 1.0
            
            # Boost recently used items
            if item.last_used_at:
                days_ago = (datetime.utcnow() - item.last_used_at).days
                if days_ago < 7:
                    score += 0.5
            
            # Boost frequently used items
            if item.usage_count > 0:
                score += min(item.usage_count * 0.1, 1.0)
            
            if score > 0:
                suggestions.append({
                    'item_id': str(item.id),
                    'name': item.name,
                    'description': item.description,
                    'content_type': item.content_type,
                    'token_count': item.token_count,
                    'relevance_score': score,
                    'usage_count': item.usage_count,
                    'last_used_at': item.last_used_at.isoformat() if item.last_used_at else None
                })
        
        # Sort by relevance score and return top results
        suggestions.sort(key=lambda x: x['relevance_score'], reverse=True)
        return suggestions[:limit]
    
    @staticmethod
    def get_user_stats() -> Dict[str, Any]:
        """Get user context statistics"""
        
        user_id = ContextService.get_user_id()
        
        total_items = ContextItem.query.filter_by(user_id=user_id, is_active=True).count()
        
        # Get most used item
        most_used = ContextItem.query.filter_by(
            user_id=user_id, 
            is_active=True
        ).order_by(ContextItem.usage_count.desc()).first()
        
        # Get total tokens
        total_tokens = db.session.query(db.func.sum(ContextItem.token_count)).filter_by(
            user_id=user_id, 
            is_active=True
        ).scalar() or 0
        
        return {
            'total_items': total_items,
            'total_tokens': int(total_tokens),
            'most_used_item': {
                'id': str(most_used.id),
                'name': most_used.name,
                'usage_count': most_used.usage_count
            } if most_used else None
        }