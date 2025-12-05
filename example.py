import re
from bs4 import BeautifulSoup
import json
import os

# ----------------- LaTeX Conversion Utility ----------------- #

def convert_plain_math_to_latex(text):
    """
    Converts recognized plain math patterns in a text block into KaTeX-compatible LaTeX
    and wraps the expression in inline delimiters (\(...\)).
    """
    if not text:
        return text

    # Remove zero-width spaces and non-breaking spaces
    text = re.sub(r'[\u200b\u200c\u200d\u00a0]', '', text).strip()
    if not text:
        return text

    # Skip if already wrapped (prevents double wrapping)
    if text.startswith(r'\(') and text.endswith(r'\)'):
        return text

    original_text = text
    
    # 1. Standard Symbol Replacements
    text = text.replace('α', '\\alpha')
    text = text.replace('β', '\\beta')
    text = text.replace('γ', '\\gamma')
    text = text.replace('θ', '\\theta')
    text = text.replace('Ω', '\\Omega')
    text = text.replace('π', '\\pi')
    text = text.replace('→', '\\vec')  # Intermediate replacement
    text = text.replace('^', '\\hat')   # Intermediate replacement
    text = text.replace('∆', '\\Delta')

    # 2. Fractions: a/b or a∕b. Looks for terms separated by slash.
    # This pattern is aggressive but necessary for cleaning the specific raw input style.
    text = re.sub(r'([a-zA-Z0-9\(\)\-]+)\s*[∕/]\s*([a-zA-Z0-9\(\)\-]+)', r'\\frac{\1}{\2}', text)

    # 3. Square Roots: √something or sqrt(something)
    text = re.sub(r'√\s*([a-zA-Z0-9\(\) {}+-]+)', r'\\sqrt{\1}', text)
    text = re.sub(r'sqrt\s*([a-zA-Z0-9\(\) {}+-]+)', r'\\sqrt{\1}', text)

    # 4. Powers and Subscripts (most dangerous part, relies on context)
    # Convert 'circ' or '∘' to degree symbol
    text = re.sub(r'(\d+)\s*circ|(\d+)°|(\d+)∘', r'^{\\circ}', text)
    
    # Subscripts: u0 -> u_{0}, T1 -> T_{1}. Avoid units like ms, cm, kg.
    text = re.sub(r'\b(?!mH|mA|ms|cm|kg|gm|rad|mol|nm|eV|atm)([a-zA-Z])(\d+)\b', r'\1_{\2}', text)
    
    # Powers/Exponents: x2 -> x^{2} (less common in the raw data, handled by subscript)
    # The raw data often mixes subscripts and superscripts, e.g., v12. We must assume the user intends v_1^2 or v^12.
    # We rely on the subscript cleanup above and leave simple numbers alone to prevent over-formatting.

    # 5. Functions & Commands
    text = re.sub(r'tan', r'\\tan', text)
    text = re.sub(r'sin', r'\\sin', text)
    text = re.sub(r'cos', r'\\cos', text)
    text = re.sub(r'log', r'\\log', text)
    text = re.sub(r'ln', r'\\ln', text)

    # 6. Final Vector Cleanup (after base letter replacement)
    text = re.sub(r'\\vec([a-zA-Z0-9]+)', r'\\vec{\1}', text)
    text = re.sub(r'\\hat([a-zA-Z])', r'\\hat{\1}', text)
    
    # 7. Wrapping Heuristic: If it contains operators, numbers, or LaTeX commands, wrap it.
    if re.search(r'[=+\-*/\d]|\\(sqrt|vec|hat|frac|tan|sin|cos|log|ln)', text) or re.search(r'E_{', text):
        return r'\(' + text + r'\)'
        
    return original_text

def apply_latex_conversion_to_html(html_content):
    """
    Safely applies the LaTeX conversion to all plain text nodes within an HTML snippet,
    preserving all tags.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # Iterate over all text nodes that are descendants of the current element
    for node in soup.find_all(string=True):
        # Only process text nodes that are not inside script or style tags
        if node.parent.name not in ['script', 'style']:
            converted_text = convert_plain_math_to_latex(str(node))
            if converted_text != str(node):
                node.replace_with(converted_text)

    # Return the modified HTML content
    return str(soup.decode_contents())


# ----------------- Aggressive Cleanup Utility (Integrated) ----------------- #

def clean_html_and_extract_math_text(html_content):
    """
    Cleans HTML structure and then applies LaTeX conversion to the resulting text nodes.
    (This function remains mostly the user's original logic for structural cleanup.)
    """
    if not html_content: 
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Heuristically extract math content/source before tags are destroyed
    # This part is complex due to proprietary tags like fmath/mjx-container.
    # We will prioritize the LaTeX conversion function later. For now, just extract text.
    math_tags = soup.find_all(['fmath', 'mjx-container'])
    for math_tag in math_tags:
        math_text = math_tag.get_text(strip=True)
        math_tag.replace_with(math_text)
            
    # 2. Aggressively strip attributes and proprietary/redundant tags
    for tag in soup.find_all(True):
        if tag.name not in ['img', 'a']:
            tag.attrs = {}
        else:
            attrs_to_keep = {'src', 'alt', 'href'}
            cleaned_attrs = {}
            for k, v in list(tag.attrs.items()):
                if k in attrs_to_keep:
                    # Normalize to string
                    v_str = str(v).strip()
                    # Strong clean: strip trailing backslashes on URLs
                    if k in ('src', 'href'):
                        v_str = v_str.rstrip('\\').strip()
                    cleaned_attrs[k] = v_str
            tag.attrs = cleaned_attrs
            
    # Discard all remaining proprietary/redundant tags
    discard_tags = ['div', 'span', 'h6', 'table', 'tr', 'td', 'style', 'script',
                    'input', 'label', 'form']
    for tag_name in discard_tags:
        for tag in soup.find_all(tag_name):
            if tag.name in ['style', 'script']:
                tag.decompose()
            else:
                tag.unwrap()
            
    # 3. Final structural cleanup and LaTeX conversion
    
    # Convert all math in place using the new function
    cleaned_html = apply_latex_conversion_to_html(str(soup.decode_contents()))
    
    # Post-conversion cleanup
    cleaned_html = re.sub(r'\s{2,}', ' ', cleaned_html).strip()
    cleaned_html = re.sub(r'(<br\s*/?>\s*){2,}', '<br/>', cleaned_html).strip()
    cleaned_html = cleaned_html.replace("<br>", "<br/>")

    # EXTRA SAFETY: remove stray "\" right after URLs inside src/href or text
    cleaned_html = re.sub(
        r'(https?://[^\s"\'<>]+)\\+(?=(["\'\s>]))',
        r'\1\2',
        cleaned_html
    )

    # 4. Ensure content starts with a block-level tag like <p> if it's not empty
    block_tags = ['<p', '<img', '<ul', '<ol', '<li', '<br', '<strong', '<em', '<a', '<h1', '<h2', '<h3', '<h4', '<h5']
    
    lower_html = cleaned_html.lower()
    if cleaned_html and not any(lower_html.startswith(tag) for tag in block_tags):
        cleaned_html = f"<p>{cleaned_html}</p>"

    return cleaned_html


# ----------------- Question Extractor ----------------- #

def extract_question_data(question_tag):
    """
    Extracts structured question data from a single HTML <li> question node,
    applying aggressive cleanup and math conversion.
    """

    data = {}
    correct_option_index = None

    # 1. Header info: subject and question number (User's original logic)
    header_div = question_tag.select_one(".ques-no")
    q_no = None
    subject = None
    if header_div:
        h6 = header_div.select_one("h6")
        if h6:
            strong = h6.find("strong")
            if strong:
                strong_text = strong.get_text(strip=True)
                m = re.search(r"(\d+)", strong_text)
                if m:
                    q_no = int(m.group(1))
            text_parts = [t.strip() for t in h6.strings if t.strip()]
            if text_parts:
                subject = re.sub(r"^\W+", "", text_parts[-1]).strip()
    
    data["subject"] = subject
    data["question_no"] = q_no
    data["question_type"] = "MCQ"

    # 2. QUESTION HTML 
    question_html = ""
    qsn_blocks = question_tag.select(".qsn-here")
    if qsn_blocks:
        parts = [blk.decode_contents() for blk in qsn_blocks if blk.decode_contents().strip()]
        if parts:
            question_html = clean_html_and_extract_math_text("".join(parts))
    
    if not question_html or len(question_html) < 50:
        mquestion_div = question_tag.select_one("#mquestion")
        if mquestion_div:
            question_html = clean_html_and_extract_math_text(mquestion_div.decode_contents())

    data["question"] = question_html.strip()

    # 3. OPTIONS 
    options = {}
    option_groups = question_tag.select('div[id^="formGroupOption"]')

    for idx, option_group in enumerate(option_groups):
        opt_index = chr(ord("A") + idx)
        
        if "correct-active" in option_group.get("class", []):
            correct_option_index = opt_index

        option_soup = BeautifulSoup(str(option_group), "html.parser")
        index_span = option_soup.select_one(".optionIndex")
        if index_span:
            opt_index = index_span.get_text(strip=True)
            index_span.decompose()

        main_div = option_soup.find("div", id=re.compile(r"^formGroupOption"))
        raw_html = ""
        if main_div:
            label_tag = main_div.select_one("label")
            if label_tag:
                raw_html = label_tag.decode_contents().strip()
            else:
                raw_html = main_div.decode_contents().strip()

        # Clean HTML (removes tags, fixes structure)
        option_html = clean_html_and_extract_math_text(raw_html).strip()
        
        # Options are generally short and should be wrapped as a single math block if they look like math
        if re.search(r'\\(sqrt|frac|tan|sin|cos|log|ln|[a-z]_\d+)', option_html, re.IGNORECASE):
             option_text = apply_latex_conversion_to_html(option_html)
        else:
             option_text = option_html
             
        # Remove the <p> wrapper if it was added for the option content (Options should be inline)
        if option_text.startswith('<p>') and option_text.endswith('</p>'):
            option_text = option_text[3:-4].strip()

        options[opt_index] = option_text.strip()

    data["options"] = options
    data["correct_answer"] = correct_option_index

    # 4. SOLUTION 
    solution_div = question_tag.select_one(".qn-solution")
    solution_html = ""
    if solution_div:
        # The key change is that clean_html_and_extract_math_text now runs the LaTeX conversion
        solution_html = clean_html_and_extract_math_text(solution_div.decode_contents())

    solution_html = re.sub(r"<strong>Solution:</strong>", "", solution_html, flags=re.IGNORECASE).strip()
    solution_html = re.sub(r"<p>Solutions</p>", "", solution_html, flags=re.IGNORECASE).strip()

    data["solution"] = solution_html

    return data


# ----------------- Main ----------------- #

def main():
    """
    Read input.txt, parse HTML, extract questions into output.json.
    """
    input_file = "input.txt"
    output_file = "output.json"
    
    # If input file doesn't exist, create a placeholder
    if not os.path.exists(input_file):
        html_snippet = """
        <ol>
            <li id="questionBox_1">
                <div class="ques-no"><h6><strong>Q.1</strong> JEE Advanced 2023 Paper - 1</h6></div>
                <div class="qsn-here"><p>A slide... coefficient of restitution of the ground is 1∕√3. Which of the following statement(s) is(are) correct?</p><img src="..."/></div>
                <div class="qn-solution">
                    <p>Solutions <strong><br/></strong> u0=√2gh <br/> vz=√2g(3h)<br/>tan‌θ=‌vzu=√3<br/>θ=60∘<br/>d=u0T=u0√2(‌3hg)=√(2gh)√(2)(‌3hg) <br/> Velocity after collision, only velocity along z-direction change<br/>v1=evz=√2gh<br/>→v=v1^k+u0^i<br/>=√2gh[^i+^k]<br/>h1=‌v122g=h<br/>Finally, u0=√2gh,θ=60∘,‌dh=2√3</p>
                </div>
                <!-- ... options etc ... -->
            </li>
        </ol>
        """
        with open(input_file, "w", encoding="utf-8") as f:
            f.write(html_snippet)
        print("A test file has been created (`input.txt`). Replace its contents with your full HTML source to run the full extraction.")
        
    print(f"Reading HTML content from {input_file}...")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    full_soup = BeautifulSoup(html_content, "html.parser")

    all_questions = full_soup.select('li[id^="questionBox"]')
    if not all_questions:
        print("No question blocks found (e.g., li[id^='questionBox']). Exiting.")
        return

    print(f"Found {len(all_questions)} question(s) to process.")

    all_extracted_data = []
    for idx, question_tag in enumerate(all_questions):
        try:
            extracted_data = extract_question_data(question_tag)
            all_extracted_data.append(extracted_data)
            print(
                f"Successfully processed question {extracted_data.get('question_no', idx + 1)} "
                f"with subject '{extracted_data.get('subject')}'."
            )
        except Exception as e:
            print(f"Error processing question at index {idx}: {e}")

    # Save JSON
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_extracted_data, f, ensure_ascii=False, indent=2)
        print(
            f"\nSuccessfully extracted data for {len(all_extracted_data)} question(s) and saved to {output_file}."
        )
    except Exception as e:
        print(f"Error writing to output file: {e}")


if __name__ == "__main__":
    main()