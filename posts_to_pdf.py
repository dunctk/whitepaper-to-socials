#!/usr/bin/env python3
"""
LinkedIn Posts to PDF Generator

This script fetches LinkedIn posts from NocoDB and generates a PDF with
LinkedIn-style layout (image + post content) with one post per page.
"""

import os
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import click
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.colors import HexColor
from PIL import Image
import tempfile
import io

# Load environment variables
load_dotenv()


class LinkedInPostsPDFGenerator:
    def __init__(self, output_filename: str = None):
        # Create output directory if it doesn't exist
        output_dir = Path("pdf_outputs")
        output_dir.mkdir(exist_ok=True)
        
        if output_filename:
            self.output_filename = str(output_dir / output_filename)
        else:
            self.output_filename = str(output_dir / f"linkedin_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        # NocoDB configuration
        self.nocodb_base_url = os.getenv("NOCODB_BASE_URL")
        self.nocodb_api_key = os.getenv("NOCODB_API_KEY")
        self.nocodb_table_id = os.getenv("NOCODB_TABLE_ID")
        
        # PDF settings
        self.page_width, self.page_height = A4
        self.margin = 0.75 * inch
        self.content_width = self.page_width - 2 * self.margin
        self.linkedin_box_width = 5 * inch  # Narrow LinkedIn-style box
        self.linkedin_box_offset = (self.content_width - self.linkedin_box_width) / 2
        
        # Create custom styles
        self.styles = self._create_styles()
        
    def _create_styles(self):
        """Create custom styles for LinkedIn-like formatting"""
        styles = getSampleStyleSheet()
        
        # LinkedIn post style
        linkedin_post_style = ParagraphStyle(
            'LinkedInPost',
            parent=styles['Normal'],
            fontSize=11,
            leading=16,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=6,
            alignment=TA_LEFT,
            fontName='Helvetica'
        )
        
        # LinkedIn metadata style
        linkedin_meta_style = ParagraphStyle(
            'LinkedInMeta',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=12,
            alignment=TA_LEFT,
            fontName='Helvetica',
            textColor=HexColor('#666666')
        )
        
        styles.add(linkedin_post_style)
        styles.add(linkedin_meta_style)
        
        return styles
    
    def _fetch_posts_from_nocodb(self) -> List[Dict]:
        """Fetch all posts from NocoDB"""
        if not all([self.nocodb_base_url, self.nocodb_api_key, self.nocodb_table_id]):
            raise ValueError("NocoDB configuration incomplete")
        
        headers = {
            'xc-token': self.nocodb_api_key
        }
        
        # Fetch all posts with full attachment info, sorted by creation date
        url = f"{self.nocodb_base_url}/api/v2/tables/{self.nocodb_table_id}/records?limit=1000&sort=CreatedAt&fields=*"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            posts = data.get('list', [])
            
            click.echo(f"Fetched {len(posts)} posts from NocoDB")
            return posts
            
        except Exception as e:
            click.echo(f"Error fetching posts from NocoDB: {e}", err=True)
            return []
    
    def _get_local_image_path(self, post_data: Dict) -> Optional[str]:
        """Get local image path using image_filename from NocoDB"""
        image_filename = post_data.get('image_filename')
        if image_filename:
            local_image_path = Path(f"content_inputs/images/{image_filename}")
            if local_image_path.exists():
                return str(local_image_path)
            else:
                click.echo(f"Local image not found: {local_image_path}")
        
        # Fallback to image_index if filename not available
        image_index = post_data.get('image_index')
        if image_index is not None:
            local_image_path = Path(f"content_inputs/images/images-{image_index}.png")
            if local_image_path.exists():
                click.echo(f"Using fallback image: {local_image_path}")
                return str(local_image_path)
        
        return None
    
    def _create_linkedin_post_elements(self, post_data: Dict) -> List:
        """Create reportlab elements for a single LinkedIn post"""
        elements = []
        
        # Add some top spacing
        elements.append(Spacer(1, 0.5 * inch))
        
        # LinkedIn-style header
        header_text = "LinkedIn Post"
        header_para = Paragraph(header_text, self.styles['LinkedInMeta'])
        elements.append(header_para)
        elements.append(Spacer(1, 0.2 * inch))
        
        # Add image if available
        image_path = self._get_local_image_path(post_data)
        if image_path:
            try:
                # Open image to get dimensions
                with Image.open(image_path) as img:
                    img_width, img_height = img.size
                
                # Calculate scaled dimensions to fit in LinkedIn box
                max_width = self.linkedin_box_width - 40  # Account for padding
                max_height = 3 * inch  # Maximum height for image
                
                # Scale image proportionally
                scale_w = max_width / img_width
                scale_h = max_height / img_height
                scale = min(scale_w, scale_h)
                
                scaled_width = img_width * scale
                scaled_height = img_height * scale
                
                # Create reportlab image
                rl_image = RLImage(image_path, width=scaled_width, height=scaled_height)
                elements.append(rl_image)
                elements.append(Spacer(1, 0.2 * inch))
                
                # Clean up temp file (only if it's a downloaded temp file)
                if image_path.startswith('/tmp') or image_path.startswith(tempfile.gettempdir()):
                    os.unlink(image_path)
                
            except Exception as e:
                click.echo(f"Error processing image: {e}", err=True)
        
        # Add post content
        post_content = post_data.get('post', '')
        if post_content:
            # Split by paragraphs and create paragraph elements
            paragraphs = post_content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    # Clean up the paragraph and handle line breaks
                    para_text = para.strip()
                    # Replace single newlines with double spaces for proper line breaks
                    para_text = para_text.replace('\n', '  <br/>')
                    para_element = Paragraph(para_text, self.styles['LinkedInPost'])
                    elements.append(para_element)
                    elements.append(Spacer(1, 0.1 * inch))
        
        return elements
    
    def generate_pdf(self):
        """Generate PDF with all LinkedIn posts"""
        # Fetch posts
        posts = self._fetch_posts_from_nocodb()
        
        if not posts:
            click.echo("No posts found to generate PDF")
            return
        
        # Create PDF document
        doc = SimpleDocTemplate(
            self.output_filename,
            pagesize=A4,
            rightMargin=self.margin,
            leftMargin=self.margin,
            topMargin=self.margin,
            bottomMargin=self.margin
        )
        
        story = []
        
        # Process each post
        for i, post in enumerate(posts):
            click.echo(f"Processing post {i+1}/{len(posts)}")
            
            # Show progress
            image_filename = post.get('image_filename', 'unknown')
            click.echo(f"Post {i+1}: Using image {image_filename}")
            
            # Create elements for this post
            post_elements = self._create_linkedin_post_elements(post)
            story.extend(post_elements)
            
            # Add page break after each post (except the last one)
            if i < len(posts) - 1:
                story.append(Spacer(1, 0.5 * inch))
                story.append(PageBreak())
        
        # Build PDF
        try:
            doc.build(story)
            click.echo(f"PDF generated successfully: {self.output_filename}")
            
        except Exception as e:
            click.echo(f"Error generating PDF: {e}", err=True)


# Import PageBreak after other imports
from reportlab.platypus import PageBreak


@click.command()
@click.option('--output', '-o', help='Output PDF filename')
def main(output):
    """Generate PDF from LinkedIn posts stored in NocoDB"""
    
    # Check required environment variables
    required_vars = ['NOCODB_API_KEY', 'NOCODB_BASE_URL', 'NOCODB_TABLE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        click.echo(f"Missing required environment variables: {', '.join(missing_vars)}", err=True)
        return
    
    generator = LinkedInPostsPDFGenerator(output)
    generator.generate_pdf()


if __name__ == '__main__':
    main()