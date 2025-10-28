"""
Math Visualization Service
Generates educational diagrams for math problems using matplotlib
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
from PIL import Image

class MathVisualizer:
    """Generate mathematical diagrams to illustrate solutions"""
    
    def __init__(self):
        self.figure_size = (10, 6)
        self.dpi = 100
    
    def generate_diagram(self, question: str, response: str) -> str:
        """
        Generate a diagram based on the math question and response.
        Returns base64 encoded PNG image.
        """
        try:
            # Detect the type of math problem
            question_lower = question.lower()
            
            # Geometry - angles
            if any(word in question_lower for word in ['angle', 'degree', 'right angle', '90']):
                fig = self._create_angle_diagram(question, response)
            
            # Basic arithmetic - multiplication/division
            elif any(word in question_lower for word in ['multiply', 'times', '×', 'multiply', 'groups']):
                fig = self._create_multiplication_diagram(question, response)
            
            # Geometry - shapes
            elif any(word in question_lower for word in ['square', 'rectangle', 'circle', 'triangle', 'sides', 'perimeter', 'area']):
                fig = self._create_shape_diagram(question, response)
            
            # Fractions
            elif any(word in question_lower for word in ['fraction', 'half', 'third', 'quarter', 'divided']):
                fig = self._create_fraction_diagram(question, response)
            
            # Survey/percentage/statistics
            elif any(word in question_lower for word in ['percent', 'percentage', '%', 'survey', 'statistics', 'population', 'sample']):
                fig = self._create_percentage_diagram(question, response)
            # Graphs/functions
            elif any(word in question_lower for word in ['graph', 'plot', 'line', 'parabola', 'function', 'equation']):
                fig = self._create_graph_diagram(question, response)
            
            # Default: simple bar chart or text diagram
            else:
                fig = self._create_default_diagram(question, response)
            
            # Convert to base64
            return self._figure_to_base64(fig)
        
        except Exception as e:
            print(f"Error generating diagram: {e}")
            return None
    
    def _create_angle_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a diagram showing angles"""
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        # Draw a right angle example
        ax.set_xlim(-0.5, 3)
        ax.set_ylim(-0.5, 3)
        ax.set_aspect('equal')
        
        # Draw right angle lines
        ax.plot([0, 2], [0, 0], 'b-', linewidth=2, label='Horizontal')
        ax.plot([0, 0], [0, 2], 'r-', linewidth=2, label='Vertical')
        
        # Draw small square in corner to show right angle
        square_size = 0.3
        square = plt.Rectangle((0, 0), square_size, square_size, fill=False, edgecolor='black', linewidth=1)
        ax.add_patch(square)
        
        # Add angle label
        ax.text(0.5, 0.5, '90°', fontsize=14, weight='bold', color='green')
        
        # Add title and description
        ax.set_title('Right Angle: 90 Degrees', fontsize=16, weight='bold')
        ax.text(1, 2.5, 'A right angle is formed where two perpendicular lines meet', 
                fontsize=11, ha='center', style='italic')
        
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def _create_multiplication_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a diagram for multiplication using groups"""
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        # Example: 5 × 3 = 15
        # Try to extract numbers from question
        import re
        numbers = re.findall(r'\d+', question)
        
        if len(numbers) >= 2:
            groups = int(numbers[0])
            items_per_group = int(numbers[1])
        else:
            groups = 5
            items_per_group = 3
        
        # Limit for visual clarity
        groups = min(groups, 8)
        items_per_group = min(items_per_group, 8)
        
        # Draw groups of items
        spacing = 1.2
        item_size = 0.3
        
        for g in range(groups):
            for i in range(items_per_group):
                circle = plt.Circle((g * spacing + i * 0.4, i * 0.4), item_size/2, 
                                   color='steelblue', alpha=0.7, edgecolor='navy', linewidth=2)
                ax.add_patch(circle)
        
        ax.set_xlim(-1, groups * spacing + 1)
        ax.set_ylim(-1, items_per_group * 0.5 + 1)
        ax.set_aspect('equal')
        
        # Add title
        result = groups * items_per_group
        ax.set_title(f'{groups} × {items_per_group} = {result}', fontsize=16, weight='bold')
        ax.text(groups * spacing / 2, -0.5, f'{groups} groups of {items_per_group} items', 
                fontsize=11, ha='center', style='italic')
        
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def _create_shape_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a diagram for geometric shapes"""
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        question_lower = question.lower()
        
        if 'square' in question_lower:
            # Draw a square
            square = plt.Rectangle((1, 1), 2, 2, fill=True, facecolor='lightblue', 
                                  edgecolor='navy', linewidth=2)
            ax.add_patch(square)
            ax.set_title('Square: 4 Equal Sides', fontsize=16, weight='bold')
            ax.text(2, 0.5, 'All sides equal • All angles 90°', fontsize=11, ha='center')
            
        elif 'triangle' in question_lower:
            # Draw a triangle
            triangle = plt.Polygon([(1, 1), (3, 1), (2, 3)], closed=True, 
                                  facecolor='lightcoral', edgecolor='darkred', linewidth=2)
            ax.add_patch(triangle)
            ax.set_title('Triangle: 3 Sides', fontsize=16, weight='bold')
            ax.text(2, 0.2, 'Sum of angles = 180°', fontsize=11, ha='center')
            
        elif 'circle' in question_lower:
            # Draw a circle
            circle = plt.Circle((2, 2), 1, facecolor='lightgreen', edgecolor='darkgreen', linewidth=2)
            ax.add_patch(circle)
            ax.plot([2, 2], [2, 3], 'k--', linewidth=1)
            ax.text(2.2, 2.5, 'radius', fontsize=10)
            ax.set_title('Circle: 360 Degrees', fontsize=16, weight='bold')
            ax.text(2, 0.2, 'All points equidistant from center', fontsize=11, ha='center')
        
        else:
            # Rectangle default
            rect = plt.Rectangle((1, 1), 3, 2, fill=True, facecolor='lightyellow', 
                                edgecolor='orange', linewidth=2)
            ax.add_patch(rect)
            ax.set_title('Rectangle: 4 Sides', fontsize=16, weight='bold')
            ax.text(2.5, 0.2, 'Opposite sides equal • All angles 90°', fontsize=11, ha='center')
        
        ax.set_xlim(0, 4)
        ax.set_ylim(0, 4)
        ax.set_aspect('equal')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def _create_fraction_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a diagram for fractions"""
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        # Draw a fraction bar
        num_sections = 4
        filled_sections = 1
        
        if '1/2' in question or 'half' in question.lower():
            num_sections = 2
            filled_sections = 1
        elif '1/3' in question or 'third' in question.lower():
            num_sections = 3
            filled_sections = 1
        elif '1/4' in question or 'quarter' in question.lower():
            num_sections = 4
            filled_sections = 1
        elif '3/4' in question:
            num_sections = 4
            filled_sections = 3
        elif '2/3' in question:
            num_sections = 3
            filled_sections = 2
        
        # Draw fraction visualization
        bar_height = 0.5
        section_width = 3 / num_sections
        
        for i in range(num_sections):
            color = 'steelblue' if i < filled_sections else 'lightgray'
            rect = plt.Rectangle((i * section_width, 1), section_width - 0.1, bar_height, 
                                facecolor=color, edgecolor='navy', linewidth=2)
            ax.add_patch(rect)
        
        # Add label
        frac_label = f'{filled_sections}/{num_sections}'
        ax.set_title(f'Fraction: {frac_label}', fontsize=16, weight='bold')
        ax.text(1.5, 0.3, f'{filled_sections} out of {num_sections} parts', 
                fontsize=11, ha='center', style='italic')
        
        ax.set_xlim(-0.5, 3.5)
        ax.set_ylim(0, 2)
        ax.set_aspect('equal')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def _create_graph_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a simple coordinate graph"""
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        # Create coordinate system
        x = np.linspace(-5, 5, 100)
        y = 2 * x  # Simple linear equation
        
        ax.plot(x, y, 'b-', linewidth=2, label='y = 2x')
        ax.axhline(y=0, color='k', linewidth=0.5)
        ax.axvline(x=0, color='k', linewidth=0.5)
        ax.grid(True, alpha=0.3)
        
        ax.set_xlabel('X axis', fontsize=11)
        ax.set_ylabel('Y axis', fontsize=11)
        ax.set_title('Coordinate Graph', fontsize=16, weight='bold')
        ax.legend(fontsize=11)
        
        plt.tight_layout()
        return fig
    
    def _create_default_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a default text-based diagram"""
        fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
        
        # Truncate response if too long
        response_text = response[:200] + '...' if len(response) > 200 else response
        
        ax.text(0.5, 0.7, 'Math Problem Solution', fontsize=16, weight='bold', 
               ha='center', transform=ax.transAxes)
        ax.text(0.5, 0.5, response_text, fontsize=11, ha='center', va='center',
               wrap=True, transform=ax.transAxes, style='italic')
        
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        plt.tight_layout()
        return fig

    def _create_percentage_diagram(self, question: str, response: str) -> plt.Figure:
        """Create a simple pie chart for survey/percentage data"""
        import re
        fig, ax = plt.subplots(figsize=(8, 6), dpi=self.dpi)

        text = f"{question}\n{response}"
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        percent = float(match.group(1)) if match else 50.0
        percent = max(0.0, min(100.0, percent))
        remainder = 100.0 - percent

        has_label = 'smartphone' in question.lower() or 'phone' in question.lower()
        label_yes = 'Have smartphones' if has_label else 'Group A'
        label_no = 'Do not have' if has_label else 'Group B'

        data = [percent, remainder]
        labels = [f"{label_yes} ({percent:.0f}%)", f"{label_no} ({remainder:.0f}%)"]
        colors = ['#2ecc71', '#e0e0e0']

        wedges, texts = ax.pie(data, colors=colors, startangle=90, wedgeprops=dict(width=0.5))
        ax.legend(wedges, labels, loc='center left', bbox_to_anchor=(1, 0.5), frameon=False)

        title = 'Survey result'
        if has_label:
            title = 'Smartphone ownership among surveyed group'
        ax.set_title(title, fontsize=16, weight='bold')
        ax.text(0, 0, f"{percent:.0f}%", ha='center', va='center', fontsize=18, weight='bold', color='#2c3e50')

        ax.set_aspect('equal')
        plt.tight_layout()
        return fig
    
    def _figure_to_base64(self, fig: plt.Figure) -> str:
        """Convert matplotlib figure to base64 encoded PNG"""
        try:
            # Save to buffer
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            
            # Convert to base64
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            buffer.close()
            
            return image_base64
        except Exception as e:
            print(f"Error converting figure to base64: {e}")
            plt.close(fig)
            return None
