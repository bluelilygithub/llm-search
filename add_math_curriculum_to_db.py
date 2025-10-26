#!/usr/bin/env python3
"""
Add NSW Math Curriculum and Cluey Learning worksheets content to the database.
This content will be automatically available for all math projects.
"""

import sys
from app import app, db
from models import ContextItem
import uuid

NSW_CURRICULUM_CONTENT = """
# NSW Mathematics K-10 Syllabus (2022) - Overview

## Organisation of Mathematics K-10

The syllabus structure illustrates the important role Working mathematically plays across all areas of mathematics and reflects the strengthened connections between concepts.

Mathematics K-10 outcomes and their related content are organised in:
- Number and algebra
- Measurement and space
- Statistics and probability

## Working Mathematically

The Working mathematically processes present in the Mathematics K-10 syllabus are:
- communicating
- understanding and fluency
- reasoning
- problem solving

Students learn to work mathematically by using these processes in an interconnected way. The coordinated development of these processes results in students becoming mathematically proficient.

When students are Working mathematically it is important to help them to reflect on how they have used their thinking to solve problems. This assists students to develop 'mathematical habits of mind' (Cuoco et al. 2010).

## Overarching Working Mathematically Outcome

A student develops understanding and fluency in mathematics through:
- exploring and connecting mathematical concepts
- choosing and applying mathematical techniques to solve problems
- communicating their thinking and reasoning coherently and clearly

The Working mathematically processes should be embedded within the concepts being taught. Embedding Working mathematically ensures students are able to fluently understand concepts and make connections to other focus areas.

## Stages of Learning

**K-6 Stages:**
- Early Stage 1 (Kindergarten)
- Stage 1 (Years 1-2)
- Stage 2 (Years 3-4)
- Stage 3 (Years 5-6)

**7-10 Stages:**
- Stage 4 (Years 7-8)
- Stage 5 (Years 9-10)

## K-6 Parts A and B

To assist programming, content in Mathematics K-6 has been separated into 2 parts, A and B:
- Part A typically focuses on early concept development
- Part B builds on these early concepts

Teachers can choose which content from Part A and/or Part B to address, based on students' prior learning, needs and abilities.

## 7-10 Core-Paths Structure

The Core-Paths structure is designed to encourage aspiration in students and provide the flexibility needed to enable teachers to create pathways for students working towards Stage 6.

The Core outcomes provide students with the foundation for Mathematics Standard 2 in Stage 6.

Paths are used to progress students towards Stage 6 courses and may be implemented at any time in Stages 4 and 5 with careful consideration of the continuum of learning.

## Key Mathematical Content Areas

**Number and Algebra:**
- Representing numbers using place value
- Additive relations
- Multiplicative relations
- Partitioned fractions
- Algebraic equations and patterns
- Linear and non-linear relationships
- Ratios and rates

**Measurement and Space:**
- Geometric measure
- 2D spatial structure
- 3D spatial structure
- Non-spatial measure (time, money, etc.)
- Pythagoras and trigonometry
- Length, area and volume
- Geometrical properties and figures

**Statistics and Probability:**
- Data classification, visualisation and analysis
- Chance and probability
- Statistical enquiry
- Further probability

## Course Requirements 7-10

Mandatory curriculum requirements for eligibility for the award of the Record of School Achievement (RoSA) include:
- Study the Board developed Mathematics syllabus substantially in each of Years 7-10
- Complete at least 400 hours of Mathematics study by the end of Year 10

Satisfactory completion of at least 200 hours of study in Mathematics during Stage 5 (Years 9 and 10) will be recorded with a grade.

## Working at Different Stages

The content presented in a stage represents the typical knowledge, understanding and skills that students learn throughout the stage. It is acknowledged that students learn at different rates and in different ways.

Teachers are best placed to make decisions about when students need to work at, above or below stage level in relation to one or more of the outcomes.

## Addressing Outcomes in Parallel

Addressing outcomes 'in parallel' means teaching:
- multiple focus areas at the same time
- parallel content in a sequential manner
- application of knowledge, understanding and skills through interrelated focus areas

This enables teachers to efficiently teach and assess essential concepts within the syllabus content while supporting students to make connections with their learning.

## Reference

Source: NSW Education Standards Authority (NESA)
URL: https://curriculum.nsw.edu.au/learning-areas/mathematics/mathematics-k-10-2022/overview
"""

CLUEY_WORKSHEETS_CONTENT = """
# Cluey Learning - Year 10 Maths Worksheets Reference

## Overview

Cluey Learning provides free, printable Year 10 maths worksheets organised by topics, covering secondary school math skills from algebra and geometry through probability, trigonometry and more.

All worksheets are PDF documents with answers provided.

## Year 10 Maths Worksheets by Topic

### Year 10 Algebra Worksheets
- Multiply, divide, add and subtract algebraic fractions
- Operations with algebraic fractions
- Problem-solving with algebraic expressions

### Year 10 Equations Worksheets
- Solve equations with pronumerals and algebraic fractions
- Complex equation solving
- Word problems and applications

### Year 10 Geometry Worksheets
- Solve angles, triangles and angle relationships
- Geometric problem-solving
- Shape properties and theorems

### Year 10 Indices Worksheets
- Multiplication, division and negative index laws
- Index operations and simplification
- Exponential expressions

### Year 10 Probability Worksheets
- Review probability techniques including Venn diagrams
- Two-way tables and probability
- Conditional probability

### Year 10 Trigonometry Worksheets
- Use trigonometric ratios to find unknown lengths and angles
- Pythagoras theorem applications
- Triangle solving

## Why Cluey's Maths Programs Work

Cluey's Mathematics programs are structured as a series of face-to-face, online, tutor-led sessions where theory, examples and exam strategies are covered in a fun and friendly way.

**Key aspects:**
- Personalised support at student's pace
- Building on understanding of core knowledge (not rote learning)
- Practice questions consolidated with feedback
- Expert tutors available to explain until students 'get it'
- Session recordings for revision
- Detailed tutor feedback and progress reports

## Learning Approach

These programs improve numeracy skills by building on understanding of core knowledge rather than providing guides to help with rote learning.

**Benefits:**
- Access to experts for clarification
- Session recordings for revision anytime
- Detailed tutor feedback
- Progress reports
- Targeted attention to specific areas

## Reference

Source: Cluey Learning
URL: https://go.clueylearning.com.au/maths-worksheets/year-10/
"""

KHAN_ACADEMY_STYLE_CONTENT = """
# Khan Academy Instructional Style and Approach

## Overview

Khan Academy is renowned for providing clear, step-by-step educational content that helps learners build deep understanding. This guide outlines the instructional approaches that make Khan Academy effective.

## Key Instructional Principles

### 1. Step-by-Step Problem Solving

**Approach:** Break complex problems into manageable steps
**Example format:**
```
Step 1: Identify what we're trying to find
Step 2: Review what information we have
Step 3: Choose an appropriate method
Step 4: Work through the solution methodically
Step 5: Check the answer makes sense
```

**Guidance for educators:**
- Never skip steps, even if they seem "obvious"
- Explain WHY each step is being taken
- Connect each step to the previous one

### 2. Visual and Conceptual Explanations

**Approach:** Use descriptions that help students visualize concepts
**Techniques:**
- Draw mental pictures with words
- Use concrete examples before abstract concepts
- Connect new concepts to familiar ones

**Guidance:**
- "Imagine we're moving along a number line..."
- "Think of fractions as pieces of a pizza..."
- "Picture this like water flowing through pipes..."

### 3. Patient and Encouraging Tone

**Approach:** Be supportive, never condescending
**Language to use:**
- "Let's work through this together"
- "Great question!"
- "That's exactly what we need to consider"
- "Let's try another way to think about this"

**Avoid:**
- "It's simple" or "This is easy"
- "You should know this"
- Any language that might make students feel discouraged

### 4. Multiple Approaches to Same Problem

**Approach:** Show different ways to solve problems
**Why:** Different students think differently
**Format:**
```
Method 1: [Approach with reasoning]
Method 2: [Alternative approach]
Method 3: [Visual or intuitive approach]

Each method leads to the same answer, but might click better for different learners.
```

### 5. Worked Examples with Thinking Aloud

**Approach:** Show the thought process, not just the answer
**Structure:**
```
"What I'm thinking: [reasoning]
What I'm doing: [action]
Why this works: [explanation]
What I'm checking: [verification]"
```

### 6. Progressive Building of Complexity

**Approach:** Start simple, gradually increase difficulty
**Process:**
1. Start with the simplest case
2. Show the pattern or method
3. Gradually add complexity
4. Connect to related concepts

**Example:** For division
- Start: "What is 10 ÷ 2?"
- Build up: "What is 100 ÷ 20?"
- Apply: "What is 1,000 ÷ 200?"
- Relate: "Notice the pattern with place values"

### 7. Guiding Questions Instead of Direct Answers

**Approach:** Help students discover rather than tell them
**Technique:**
- "What do you think happens when...?"
- "Can you think of a similar problem you've solved?"
- "What pattern do you notice?"
- "How might we check if this is right?"

### 8. Emphasis on Understanding Over Memorization

**Approach:** Explain WHY, not just HOW
**Focus on:**
- The underlying concept or principle
- Connections to other concepts
- Real-world applications
- Logical reasoning

**Avoid:**
- Rote memorization without context
- "Just remember this rule"
- "Don't worry why, just do this"

### 9. Common Mistakes and How to Avoid Them

**Approach:** Anticipate and address frequent errors
**Format:**
```
Common mistake: [what students often get wrong]
Why this happens: [reasoning]
Correct approach: [right way to think about it]
How to avoid: [strategy]
```

### 10. Checking Work and Reasonableness

**Approach:** Always encourage verification
**Questions to ask:**
- "Does this answer make sense?"
- "Is it reasonable for the context?"
- "Can we check this another way?"
- "What would happen if we double-checked?"

## Response Format for Educators

When explaining mathematical concepts, follow this structure:

### Introduction
- Hook or real-world connection
- What we'll learn and why it matters

### Conceptual Foundation
- Build intuitive understanding first
- Use simple examples

### Step-by-Step Explanation
- Break into clear steps
- Explain reasoning for each step
- Connect steps logically

### Worked Examples
- Start with easy cases
- Progress to more complex
- Show multiple methods when helpful

### Practice Guidance
- Point out common pitfalls
- Suggest verification strategies
- Encourage experimentation

### Connection
- Link to previous learning
- Preview what comes next
- Show broader applications

## Language Patterns

### Explanatory Phrases
- "The key idea here is..."
- "Let's think about this carefully..."
- "One way to approach this..."
- "This works because..."
- "We can verify this by..."

### Encouraging Phrases
- "You're on the right track"
- "Great observation!"
- "Let's explore this together"
- "That's a good way to think about it"
- "I see you're connecting the concepts"

### Clarifying Phrases
- "To be more specific..."
- "In other words..."
- "To put it differently..."
- "Let me break this down..."
- "Another way to look at this..."

## Adapt to Learner Level

### For Struggling Students
- Provide more intermediate steps
- Use more analogies and concrete examples
- Offer multiple entry points to the concept
- Be extra encouraging

### For Advanced Students
- Provide challenges and extensions
- Connect to deeper concepts
- Explore alternative approaches
- Encourage creative problem-solving

## Assessment Approach

### Focus on:
- Process over answer
- Multiple solution paths
- Conceptual understanding
- Ability to explain reasoning

### Questions to ask:
- "How did you approach this?"
- "What was your thinking?"
- "What makes you confident this is right?"
- "Could you solve this a different way?"

## Reference

Source: Khan Academy instructional style and methodology
Website: https://www.khanacademy.org/
Khan Academy is known for free, world-class education with clear explanations and progressive learning.
"""

def add_math_context_items():
    """Add NSW curriculum and Cluey worksheets to context_items table"""
    
    with app.app_context():
        # Check if items already exist
        existing_nsw = ContextItem.query.filter_by(name="NSW Mathematics K-10 Curriculum Overview").first()
        existing_cluey = ContextItem.query.filter_by(name="Cluey Learning Year 10 Maths Worksheets").first()
        existing_khan = ContextItem.query.filter_by(name="Khan Academy Instructional Style and Approach").first()
        
        if existing_nsw and existing_cluey and existing_khan:
            print("✅ All context items already exist in the database.")
            return
        
        # Add NSW Curriculum
        if not existing_nsw:
            nsw_item = ContextItem(
                id=uuid.uuid4(),
                user_id="system",  # System-wide context item
                project_id=None,  # Available for all projects
                name="NSW Mathematics K-10 Curriculum Overview",
                description="Official NSW Mathematics K-10 Syllabus (2022) content covering curriculum structure, working mathematically processes, stages of learning, and mathematical content areas.",
                content_type="text",
                content_text=NSW_CURRICULUM_CONTENT,
                content_summary="NSW Mathematics K-10 curriculum structure, stages, working mathematically processes, and content areas",
                extra_data={"source": "NSW Education Standards Authority", "url": "https://curriculum.nsw.edu.au/learning-areas/mathematics/mathematics-k-10-2022/overview", "category": "math", "auto_load": True},
                is_active=True,
                usage_count=0
            )
            db.session.add(nsw_item)
            print("✅ Created NSW Mathematics K-10 Curriculum context item")
        
        # Add Cluey Worksheets
        if not existing_cluey:
            cluey_item = ContextItem(
                id=uuid.uuid4(),
                user_id="system",  # System-wide context item
                project_id=None,  # Available for all projects
                name="Cluey Learning Year 10 Maths Worksheets",
                description="Cluey Learning Year 10 maths worksheets covering algebra, equations, geometry, indices, probability, and trigonometry with problem-solving approaches and learning strategies.",
                content_type="text",
                content_text=CLUEY_WORKSHEETS_CONTENT,
                content_summary="Year 10 maths worksheets and learning approaches covering algebra, equations, geometry, indices, probability, and trigonometry",
                extra_data={"source": "Cluey Learning", "url": "https://go.clueylearning.com.au/maths-worksheets/year-10/", "category": "math", "auto_load": True},
                is_active=True,
                usage_count=0
            )
            db.session.add(cluey_item)
            print("✅ Created Cluey Learning Worksheets context item")
        
        # Add Khan Academy Style
        if not existing_khan:
            khan_item = ContextItem(
                id=uuid.uuid4(),
                user_id="system",  # System-wide context item
                project_id=None,  # Available for all projects
                name="Khan Academy Instructional Style and Approach",
                description="Khan Academy-style instructional approach with step-by-step problem solving, patient explanations, multiple approaches, worked examples, and emphasis on conceptual understanding.",
                content_type="text",
                content_text=KHAN_ACADEMY_STYLE_CONTENT,
                content_summary="Khan Academy instructional methodology: step-by-step problem solving, patient explanations, multiple approaches, conceptual understanding",
                extra_data={"source": "Khan Academy", "url": "https://www.khanacademy.org/", "category": "math", "auto_load": True, "instructional_style": True},
                is_active=True,
                usage_count=0
            )
            db.session.add(khan_item)
            print("✅ Created Khan Academy Instructional Style context item")
        
        try:
            db.session.commit()
            print("\n✅ Successfully added math curriculum context items to the database!")
            print("These will now be automatically available for all math projects.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding context items: {str(e)}")
            raise

if __name__ == "__main__":
    with app.app_context():
        add_math_context_items()

