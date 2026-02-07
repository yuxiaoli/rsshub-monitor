import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Render prompt with date range")
    parser.add_argument(
        "--template", 
        type=str, 
        default=r"prompts\deep_research_prompt.f-string.md",
        help="Path to the prompt template"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default=r"temp\output",
        help="Directory to save the rendered prompt"
    )
    parser.add_argument(
        "--days", 
        type=int, 
        default=7,
        help="Number of past days for the date range"
    )
    
    args = parser.parse_args()
    
    template_path = Path(args.template)
    output_dir = Path(args.output_dir)
    
    if not template_path.exists():
        print(f"Error: Template file not found at {template_path.absolute()}")
        return
        
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()
        
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    time_range = f"from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (past {args.days} days)"
    example_date = end_date.strftime('%Y-%m-%d')
    
    try:
        rendered_content = template_content.format(
            time_range=time_range, 
            example_date=example_date
        )
    except KeyError as e:
        print(f"Error rendering template: Missing key {e}")
        return
    except ValueError as e:
        print(f"Error rendering template: {e}. Check if you escaped curly braces {{}} properly.")
        return

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # We can output as rendered_prompt.md or keep original name
    # If original name ends with .f-string.md, maybe strip it
    out_name = template_path.name.replace(".f-string.md", ".md")
    if out_name == template_path.name:
        out_name = f"rendered_{template_path.name}"
        
    output_file = output_dir / out_name
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_content)
        
    print(f"Successfully rendered prompt to {output_file.absolute()}")

if __name__ == "__main__":
    main()
