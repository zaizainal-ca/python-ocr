import re
import json

def parse_mykad(ocr_result):
    """
    Parses raw PaddleOCR results into structured MyKad JSON data.
    
    PaddleOCR format:
    [
      [
        [[ [x1,y1],[x2,y2],[x3,y3],[x4,y4] ], ('text_content', confidence_score)],
        ...
      ]
    ]
    """
    # If ocr_result is empty or None
    if not ocr_result or not ocr_result[0]:
        return {}

    # Extract the first image results page
    first_page = ocr_result[0]
    
    if isinstance(first_page, dict):
        # New format (dict containing 'rec_texts' and 'rec_polys')
        rec_texts = first_page.get('rec_texts', [])
        rec_polys = first_page.get('rec_polys', [])
        
        # Combine polys and texts
        lines = []
        for poly, text in zip(rec_polys, rec_texts):
            lines.append((poly, text))
            
        # Sort by y-coordinate of the first vertex: poly[0][1]
        sorted_lines = sorted(lines, key=lambda x: x[0][0][1])
        detected_texts = [item[1].strip() for item in sorted_lines]
    else:
        # Old format (list of nested items)
        sorted_lines = sorted(first_page, key=lambda x: x[0][0][1])
        detected_texts = [item[1][0].strip() for item in sorted_lines]
    
    mykad_data = {
        "ic_number": None,
        "name": None,
        "gender": None,
        "religion": None,
        "citizenship": None,
        "state": None,
        "address": []
    }
    
    # 1. Match IC Number
    ic_pattern = re.compile(r'\d{6}-\d{2}-\d{4}')
    ic_raw_pattern = re.compile(r'\d{12}')
    ic_index = -1
    
    for idx, text in enumerate(detected_texts):
        clean_text = text.replace(" ", "")
        # Check standard format
        match = ic_pattern.search(text)
        if match:
            mykad_data["ic_number"] = match.group(0)
            ic_index = idx
            break
        # Check digit-only format
        match_raw = ic_raw_pattern.search(clean_text)
        if match_raw:
            raw_val = match_raw.group(0)
            mykad_data["ic_number"] = f"{raw_val[:6]}-{raw_val[6:8]}-{raw_val[8:]}"
            ic_index = idx
            break

    # Helper keywords
    states_list = [
        "JOHOR", "KEDAH", "KELANTAN", "MELAKA", "NEGERI SEMBILAN", 
        "PAHANG", "PERAK", "PERLIS", "PULAU PINANG", "PENANG", 
        "SABAH", "SARAWAK", "SELANGOR", "TERENGGANU", "KUALA LUMPUR", 
        "LABUAN", "PUTRAJAYA"
    ]
    
    ignore_keywords = [
        "kad", "mykad", "malaysia", "warganegara", "islam", "lelaki", "perempuan", "lela", "peremp",
        "identity", "card", "pemsensyan", "dentitly", "mmala", "warganegaha", "isnam"
    ]

    # Extract single-field attributes
    for text in detected_texts:
        clean_text = text.upper().strip()
        if "LELAKI" in clean_text or clean_text == "LELA":
            mykad_data["gender"] = "LELAKI"
        elif "PEREMPUAN" in clean_text or clean_text == "PEREMP":
            mykad_data["gender"] = "PEREMPUAN"
            
        if "ISLAM" in clean_text:
            mykad_data["religion"] = "ISLAM"
            
        if any(w in clean_text for w in ["WARGANEGARA", "WARGANEGAHA"]):
            mykad_data["citizenship"] = "WARGANEGARA"
            
        for state in states_list:
            if state in clean_text:
                mykad_data["state"] = state

    # 2. Extract Name and Address using positions relative to the IC Number
    potential_name_lines = []
    address_lines = []
    
    for idx, text in enumerate(detected_texts):
        # Start looking for Name and Address after the IC Number line
        if ic_index != -1 and idx <= ic_index:
            continue
            
        clean_text = text.upper().strip()
        
        # Skip garbage keywords
        if any(kw in clean_text.lower() for kw in ignore_keywords) or len(clean_text) < 3:
            continue
            
        # If we see religion or gender, we usually reached the end of name/address
        if clean_text in ["LELAKI", "PEREMPUAN", "ISLAM", "WARGANEGARA"]:
            continue
            
        # Name classification: Uppercase letters, spaces, and punctuation like ', ., -, / (e.g. BIBI' JUHAINAH, MOHD., A/L, A/P)
        is_name_pattern = bool(re.match(r"^[A-Z\s'\.\-\/]+$", clean_text))
        
        if is_name_pattern and len(potential_name_lines) < 2 and not any(state in clean_text for state in states_list):
            # Exclude lines containing common address keywords
            addr_kws = ["NO", "LOT", "JALAN", "TAMAN", "KAMPUNG", "KG", "KUARTERS", "SEKSYEN", "BANDAR", "BATU", "JLN", "BLOK", "BLOCK", "TINGKAT", "LEBUH"]
            if not any(addr_kw in clean_text for addr_kw in addr_kws):
                potential_name_lines.append(text)
                continue
                
        # Otherwise, treat as address line
        if clean_text not in states_list:
            address_lines.append(text)

    # Combine name lines
    if potential_name_lines:
        mykad_data["name"] = " ".join(potential_name_lines)
        
    # Ensure state is appended to the address if found
    if mykad_data["state"] and not any(mykad_data["state"] in addr.upper() for addr in address_lines):
        address_lines.append(mykad_data["state"])
        
    mykad_data["address"] = address_lines

    # --- Enhanced Address Parsing ---
    # 1. Full Address
    full_address = ", ".join(address_lines)
    mykad_data["full_address"] = full_address

    # 2. Extract Postcode and City
    postcode = None
    city = None
    postcode_line_idx = -1
    
    postcode_pattern = re.compile(r'\b\d{5}\b')
    for idx, line in enumerate(address_lines):
        match = postcode_pattern.search(line)
        if match:
            postcode = match.group(0)
            postcode_line_idx = idx
            # City is the rest of the line (excluding the postcode)
            city_part = line.replace(postcode, "").strip(" ,-")
            if city_part:
                city = city_part
            break
            
    mykad_data["postcode"] = postcode
    mykad_data["city"] = city

    # 3. Extract Address 1 and Address 2
    street_lines = []
    for idx, line in enumerate(address_lines):
        line_upper = line.upper()
        # Skip the state line
        if mykad_data["state"] and mykad_data["state"] == line_upper:
            continue
        # Skip the postcode line (usually containing postcode + city)
        if idx == postcode_line_idx:
            continue
        street_lines.append(line)
        
    # If no street lines found, fallback to using the postcode line as address_1
    if not street_lines and postcode_line_idx != -1:
        street_lines.append(address_lines[postcode_line_idx])
        
    address_1 = ""
    address_2 = ""
    
    if len(street_lines) == 1:
        address_1 = street_lines[0]
        if postcode_line_idx != -1:
            address_2 = address_lines[postcode_line_idx]
    elif len(street_lines) >= 2:
        # Split street lines in half to populate address_1 and address_2
        mid = (len(street_lines) + 1) // 2
        address_1 = ", ".join(street_lines[:mid])
        rest_street = street_lines[mid:]
        if postcode_line_idx != -1:
            rest_street.append(address_lines[postcode_line_idx])
        address_2 = ", ".join(rest_street)
    else:
        # Generic fallback
        address_1 = ", ".join(address_lines[:-1]) if len(address_lines) > 1 else (address_lines[0] if address_lines else "")
        address_2 = address_lines[-1] if len(address_lines) > 1 else ""
        
    mykad_data["address_1"] = address_1.strip(" ,-")
    mykad_data["address_2"] = address_2.strip(" ,-")
    
    # 4. Fallback gender from IC Number (Odd last digit = LELAKI, Even last digit = PEREMPUAN)
    if not mykad_data["gender"] and mykad_data["ic_number"]:
        clean_ic = mykad_data["ic_number"].replace("-", "").strip()
        if len(clean_ic) == 12 and clean_ic.isdigit():
            last_digit = int(clean_ic[-1])
            mykad_data["gender"] = "LELAKI" if last_digit % 2 != 0 else "PEREMPUAN"
            
    return mykad_data
