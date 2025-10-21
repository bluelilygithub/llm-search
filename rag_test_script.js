// RAG Testing Script - Run this in your browser's console
// Make sure you're logged into your app first

console.log('🧪 Starting RAG System Tests...');

// Test 1: Check if we have any documents to process
async function testContextItems() {
    console.log('\n📄 Test 1: Checking available documents...');
    try {
        const response = await fetch('/api/context-items');
        const data = await response.json();
        console.log(`✅ Found ${data.length} context items`);
        
        // Show first few items
        data.slice(0, 3).forEach(item => {
            console.log(`  - ${item.name} (${item.content_type}) - ${item.content_text?.length || 0} chars`);
        });
        
        return data.length > 0;
    } catch (error) {
        console.error('❌ Error checking context items:', error);
        return false;
    }
}

// Test 2: Process a document for embeddings
async function testDocumentProcessing() {
    console.log('\n⚙️ Test 2: Processing documents for embeddings...');
    try {
        const response = await fetch('/api/rag/process-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        console.log(`✅ Processing result:`, data);
        return data.success;
    } catch (error) {
        console.error('❌ Error processing documents:', error);
        return false;
    }
}

// Test 3: Test semantic search
async function testSemanticSearch() {
    console.log('\n🔍 Test 3: Testing semantic search...');
    try {
        const testQueries = [
            'What is the main topic?',
            'How does this work?',
            'What are the key points?',
            'Tell me about the process'
        ];
        
        for (const query of testQueries) {
            console.log(`  Searching for: "${query}"`);
            const response = await fetch('/api/rag/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    similarity_threshold: 0.5,
                    max_results: 3
                })
            });
            const data = await response.json();
            
            if (data.success) {
                console.log(`    ✅ Found ${data.total_results} results`);
                data.results.forEach((result, i) => {
                    console.log(`      ${i+1}. "${result.chunk_text.substring(0, 100)}..." (score: ${result.similarity_score.toFixed(3)})`);
                });
            } else {
                console.log(`    ❌ Search failed: ${data.error}`);
            }
        }
        return true;
    } catch (error) {
        console.error('❌ Error testing semantic search:', error);
        return false;
    }
}

// Test 4: Test context retrieval for AI responses
async function testContextRetrieval() {
    console.log('\n🤖 Test 4: Testing context retrieval for AI...');
    try {
        const testQuery = 'What is the main topic discussed?';
        const response = await fetch('/api/rag/get-context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: testQuery,
                max_context_length: 2000
            })
        });
        const data = await response.json();
        
        if (data.success) {
            console.log(`✅ Retrieved ${data.context_length} characters of context`);
            console.log(`📝 Context preview: "${data.context.substring(0, 200)}..."`);
            return true;
        } else {
            console.log(`❌ Context retrieval failed: ${data.error}`);
            return false;
        }
    } catch (error) {
        console.error('❌ Error testing context retrieval:', error);
        return false;
    }
}

// Run all tests
async function runAllTests() {
    console.log('🚀 Running complete RAG system test suite...\n');
    
    const results = {
        contextItems: await testContextItems(),
        documentProcessing: await testDocumentProcessing(),
        semanticSearch: await testSemanticSearch(),
        contextRetrieval: await testContextRetrieval()
    };
    
    console.log('\n📊 Test Results Summary:');
    console.log(`  Context Items Available: ${results.contextItems ? '✅' : '❌'}`);
    console.log(`  Document Processing: ${results.documentProcessing ? '✅' : '❌'}`);
    console.log(`  Semantic Search: ${results.semanticSearch ? '✅' : '❌'}`);
    console.log(`  Context Retrieval: ${results.contextRetrieval ? '✅' : '❌'}`);
    
    const allPassed = Object.values(results).every(result => result);
    console.log(`\n🎯 Overall Result: ${allPassed ? '✅ ALL TESTS PASSED!' : '❌ Some tests failed'}`);
    
    if (allPassed) {
        console.log('\n🎉 Congratulations! Your RAG pipeline is working perfectly!');
        console.log('💡 You can now:');
        console.log('   - Upload documents and they will be automatically processed');
        console.log('   - Ask questions and get relevant context from your knowledge base');
        console.log('   - Use semantic search to find specific information');
    }
}

// Start the tests
runAllTests();
