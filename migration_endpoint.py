"""
Add this to your app.py file to create a web endpoint for running the index migration
"""

@app.route('/migrate-add-indexes')
def migrate_add_indexes():
    """
    Web endpoint to add database indexes for performance
    Only run this once after deployment
    """
    try:
        import subprocess
        import sys
        
        # Log the migration attempt
        app.logger.info("Starting database index migration via web endpoint")
        
        # Run the migration script
        result = subprocess.run([
            sys.executable, 'migrate_add_indexes.py'
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        if result.returncode == 0:
            app.logger.info("Database index migration completed successfully")
            return jsonify({
                'success': True,
                'message': 'Database indexes added successfully',
                'output': result.stdout,
                'details': 'Performance indexes have been created. Your app should be faster now.'
            })
        else:
            app.logger.error(f"Database index migration failed: {result.stderr}")
            return jsonify({
                'success': False,
                'message': 'Database index migration failed',
                'error': result.stderr,
                'output': result.stdout
            }), 500
            
    except subprocess.TimeoutExpired:
        app.logger.error("Database index migration timed out")
        return jsonify({
            'success': False,
            'message': 'Migration timed out',
            'error': 'The migration took longer than 5 minutes'
        }), 500
        
    except Exception as e:
        app.logger.error(f"Error running database index migration: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to run migration',
            'error': str(e)
        }), 500


@app.route('/check-database-performance')
def check_database_performance():
    """
    Check database performance and index status
    """
    try:
        # Check if indexes exist
        from database import db
        
        # Query to check existing indexes
        index_query = """
            SELECT 
                t.relname as table_name,
                i.relname as index_name,
                pg_size_pretty(pg_relation_size(i.oid)) as size
            FROM pg_class t, pg_class i, pg_index ix
            WHERE t.oid = ix.indrelid
            AND i.oid = ix.indexrelid
            AND t.relkind = 'r'
            AND t.relname IN ('conversations', 'messages', 'projects', 'context_items')
            AND i.relname LIKE 'idx_%'
            ORDER BY t.relname, i.relname;
        """
        
        result = db.session.execute(index_query)
        indexes = [dict(row) for row in result]
        
        # Check table sizes
        size_query = """
            SELECT 
                relname as table_name,
                pg_size_pretty(pg_total_relation_size(oid)) as total_size,
                pg_size_pretty(pg_relation_size(oid)) as table_size
            FROM pg_class 
            WHERE relkind = 'r' 
            AND relname IN ('conversations', 'messages', 'projects', 'context_items')
            ORDER BY pg_total_relation_size(oid) DESC;
        """
        
        result = db.session.execute(size_query)
        table_sizes = [dict(row) for row in result]
        
        # Count records
        counts = {}
        for table in ['conversations', 'messages', 'projects', 'context_items']:
            try:
                count_result = db.session.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = count_result.scalar()
            except:
                counts[table] = 0
        
        return jsonify({
            'success': True,
            'indexes': indexes,
            'table_sizes': table_sizes,
            'record_counts': counts,
            'recommendations': {
                'has_performance_indexes': len(indexes) > 0,
                'needs_migration': len(indexes) < 5,
                'migration_url': '/migrate-add-indexes'
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error checking database performance: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
