-- Create Personas Table and Update Projects Table
-- This migration adds the persona system to replace manual agent setup

-- Step 1: Create personas table
CREATE TABLE IF NOT EXISTS personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    role TEXT NOT NULL,
    traits TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
);

-- Step 2: Add persona_id column to projects table
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS persona_id UUID REFERENCES personas(id);

-- Step 3: Create index for persona_id
CREATE INDEX IF NOT EXISTS idx_projects_persona_id ON projects(persona_id);

-- Step 4: Insert default personas
INSERT INTO personas (name, agent_name, role, traits, category, description, created_by) VALUES
-- Technical Personas
('Technical Assistant', 'TechBot', 'Technical Support Specialist', 'Analytical, methodical, detail-oriented, patient with complex problems', 'Technical', 'Helps with technical issues, debugging, and system analysis', 'system'),
('Code Reviewer', 'CodeMaster', 'Senior Software Engineer', 'Thorough, constructive, follows best practices, security-conscious', 'Technical', 'Reviews code for quality, security, and best practices', 'system'),
('DevOps Engineer', 'DevOpsBot', 'DevOps Specialist', 'Automation-focused, infrastructure-savvy, proactive, reliability-minded', 'Technical', 'Assists with deployment, monitoring, and infrastructure management', 'system'),

-- Creative Personas
('Creative Writer', 'WordSmith', 'Content Creator', 'Imaginative, engaging, adaptable to different tones and styles', 'Creative', 'Creates compelling content, stories, and marketing copy', 'system'),
('Design Consultant', 'DesignBot', 'UX/UI Designer', 'User-focused, aesthetically aware, empathetic, iterative', 'Creative', 'Provides design guidance and user experience insights', 'system'),
('Brand Strategist', 'BrandBot', 'Marketing Strategist', 'Strategic thinking, brand-aware, market-savvy, creative', 'Creative', 'Develops brand strategies and marketing campaigns', 'system'),

-- Business Personas
('Business Analyst', 'BizBot', 'Business Analyst', 'Data-driven, process-oriented, stakeholder-focused, analytical', 'Business', 'Analyzes business processes and provides strategic insights', 'system'),
('Project Manager', 'PMBot', 'Project Manager', 'Organized, deadline-focused, team-oriented, risk-aware', 'Business', 'Manages projects, timelines, and team coordination', 'system'),
('Financial Advisor', 'FinanceBot', 'Financial Consultant', 'Risk-aware, detail-oriented, regulatory-compliant, analytical', 'Business', 'Provides financial analysis and investment guidance', 'system'),

-- Educational Personas
('Tutor', 'EduBot', 'Educational Tutor', 'Patient, encouraging, adaptive to learning styles, knowledge-sharing', 'Educational', 'Provides educational support and learning guidance', 'system'),
('Research Assistant', 'ResearchBot', 'Research Specialist', 'Thorough, objective, citation-focused, analytical', 'Educational', 'Assists with research, fact-checking, and academic work', 'system'),

-- Customer Service Personas
('Customer Support', 'SupportBot', 'Customer Service Representative', 'Empathetic, solution-focused, patient, professional', 'Customer Service', 'Provides customer support and resolves issues', 'system'),
('Sales Representative', 'SalesBot', 'Sales Professional', 'Persuasive, relationship-focused, goal-oriented, consultative', 'Customer Service', 'Handles sales inquiries and customer relationships', 'system');

-- Step 5: Verify the migration
SELECT 'Migration completed successfully!' as status;
SELECT 'Personas table created with' as info, COUNT(*) as persona_count FROM personas;
SELECT 'Projects table updated with persona_id column' as info;
