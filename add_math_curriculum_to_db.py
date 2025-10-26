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

def add_math_context_items():
    """Add NSW curriculum and Cluey worksheets to context_items table"""
    
    with app.app_context():
        # Check if items already exist
        existing_nsw = ContextItem.query.filter_by(name="NSW Mathematics K-10 Curriculum Overview").first()
        existing_cluey = ContextItem.query.filter_by(name="Cluey Learning Year 10 Maths Worksheets").first()
        
        if existing_nsw and existing_cluey:
            print("✅ Both context items already exist in the database.")
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

