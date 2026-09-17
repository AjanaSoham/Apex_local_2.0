import re


ROLE_KEYWORDS = (
    "developer",
    "engineer",
    "architect",
    "manager",
    "consultant",
    "analyst",
    "designer",
    "administrator",
    "lead",
    "director",
    "scientist",
    "product owner",
)


def is_role_header(line):
    """
    Detect actual job-title lines.
    """

    line = line.strip()

    if not line:
        return False

    lower_line = line.lower()

    ignored_starts = (
        "*",
        "-",
        "•",
        "objective",
        "executive summary",
        "areas of expertise",
        "product portfolio",
        "experience",
        "education",
        "training",
        "responsibilities",
        "environment",
    )

    if lower_line.startswith(ignored_starts):
        return False

    # Job headings in this resume contain a full date range.
    role_date_pattern = (
        r"\b\d{2}/\d{4}\s+to\s+"
        r"(?:\d{2}/\d{4}|current|present)\b"
    )

    if not re.search(role_date_pattern, line, re.IGNORECASE):
        return False

    # Do not treat education as a job.
    degree_words = (
        "master",
        "bachelor",
        "phd",
        "doctorate",
        "university",
        "college",
    )

    if any(word in lower_line for word in degree_words):
        return False

    return any(keyword in lower_line for keyword in ROLE_KEYWORDS)


def split_company_and_title(line):
    """
    Splits a line containing company, title and date information.
    """

    date_pattern = (
        r"\b\d{2}/\d{4}\s+to\s+"
        r"(?:current|present|\d{2}/\d{4})\b"
    )

    date_match = re.search(
        date_pattern,
        line,
        re.IGNORECASE
    )

    date_range = ""

    if date_match:
        date_range = date_match.group(0).strip()
        line = line[:date_match.start()].strip()

    # Correct pipe separator.
    parts = re.split(r"\s{2,}|\s*\|\s*", line.strip())

    if len(parts) >= 2:
        company = parts[0].strip()
        title = " ".join(parts[1:]).strip()
    else:
        company = ""
        title = line.strip()

    return company, title


def extract_technologies(environment_text):
    """
    Converts an Environment line into a list of technologies.
    """

    if not environment_text:
        return []

    technologies = re.split(r",|;|\|", environment_text)

    return [
        tech.strip()
        for tech in technologies
        if tech.strip()
    ]


def extract_experience_blocks(lines):
    experiences = []
    unknown_lines = []

    role_pattern = re.compile(
        r"\b\d{2}/\d{4}\s+to\s+"
        r"(?:\d{2}/\d{4}|CURRENT|PRESENT)\b",
        re.IGNORECASE
    )

    degree_pattern = re.compile(
        r"\b(master|bachelor|phd|doctorate|associate|university|college)\b",
        re.IGNORECASE
    )

    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        # Detect a real job heading.
        if (
            role_pattern.search(line)
            and not degree_pattern.search(line)
            and is_role_header(line)
        ):
            role_line = line

            # Remove date range from the job title.
            job_title = role_pattern.sub("", role_line).strip()
            job_title = re.sub(r"\s+", " ", job_title)

            company = ""
            location = ""

            # The next line contains:
            # Company | City, STATE
            if i + 1 < len(lines):
                company_line = lines[i + 1].strip()

                if "|" in company_line:
                    company, location = [
                        part.strip()
                        for part in company_line.split("|", 1)
                    ]
                    i += 1
                else:
                    company = company_line
                    i += 1

            responsibilities = []
            additional_information = []

            i += 1

            # Read responsibility lines until the next job or education.
            while i < len(lines):
                current = lines[i].strip()

                if not current:
                    i += 1
                    continue

                if role_pattern.search(current):
                    break

                if degree_pattern.search(current):
                    break

                if current.upper() in {
                    "EXPERIENCE",
                    "EDUCATION",
                    "EDUCATION AND",
                    "TRAINING",
                }:
                    i += 1
                    continue

                responsibilities.append(current)
                i += 1

            experiences.append({
                "company": company,
                "job_title": job_title,
                "location": location,
                "responsibilities": responsibilities,
                "technologies": [],
                "additional_information": additional_information,
            })

        else:
            unknown_lines.append(line)
            i += 1

    return {
        "experiences": experiences,
        "unknown_lines": unknown_lines,
    }


def extract_experience_entries(text: str) -> list[dict[str, object]]:
    """Return normalized experience entries from resume text."""
    if not text or not text.strip():
        return []

    lines = [line.strip(" -*•\t") for line in text.splitlines()]
    section_heading_pattern = re.compile(
        r"(?i)^(?:experience|work experience|professional experience|employment history|career history)\s*:??\s*$"
    )

    # Focus only on the employment section when available.
    start_index = None
    for idx, line in enumerate(lines):
        if section_heading_pattern.match(line):
            start_index = idx + 1
            break

    if start_index is None:
        start_index = 0

    date_pattern = re.compile(
        r"(?i)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|(?:19|20)\d{2})\s*(?:-|–|to)\s*(?:present|current|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|(?:19|20)\d{2}))"
    )
    section_end_pattern = re.compile(
        r"(?i)^(?:education|skills|technical skills|projects|certifications|languages known|hobbies|summary)\s*:??\s*$"
    )

    entries = []
    idx = start_index
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if section_end_pattern.match(line):
            break

        if date_pattern.search(line):
            title = ""
            company = ""
            location = ""
            date_text = line

            for prev_index in range(idx - 1, max(-1, idx - 6), -1):
                candidate = lines[prev_index].strip()
                if not candidate or section_end_pattern.match(candidate):
                    continue
                if date_pattern.search(candidate):
                    continue
                if re.search(r"(?i)^(?:education|skills|projects|certifications|languages known|hobbies)\b", candidate):
                    continue
                if re.search(r"\b(?:company|university|college|school|corp|inc|llc|ltd|limited|pvt)\b|,\s*[A-Z]{2,}\b", candidate, re.IGNORECASE):
                    continue
                title = candidate
                break

            for next_index in range(idx + 1, min(len(lines), idx + 6)):
                candidate = lines[next_index].strip()
                if not candidate or section_end_pattern.match(candidate):
                    continue
                if date_pattern.search(candidate):
                    continue
                if not company:
                    company = candidate
                    continue
                if not location and re.search(r"\b(?:ny|ca|tx|fl|wa|ga|ma|il|co|india|usa|uk|germany|bengal|kolkata|new york|albany|buffalo)\b", candidate, re.IGNORECASE):
                    location = candidate
                    continue
                break

            if company and "," in company:
                company_parts = [part.strip() for part in company.split(",", 1)]
                if len(company_parts) == 2 and not re.search(r"\b(?:corp|inc|llc|ltd|university|college)\b", company_parts[0], re.IGNORECASE):
                    company_name = company_parts[0]
                    location = company_parts[1].strip() if not location else location
                    company = company_name

            if not title:
                title = company
                company = ""
            elif title.lower() == company.lower():
                title = ""

            responsibilities = []
            for next_index in range(idx + 1, len(lines)):
                candidate = lines[next_index].strip()
                if not candidate:
                    continue
                if section_end_pattern.match(candidate):
                    break
                if date_pattern.search(candidate):
                    break
                if candidate.lower() in {"experience", "professional experience", "work experience"}:
                    continue
                if candidate == company or candidate == location:
                    continue
                responsibilities.append(candidate)

            entries.append({
                "company": company,
                "job_title": title,
                "location": location,
                "responsibilities": responsibilities,
                "technologies": [],
                "additional_information": [date_text],
                "start_date": date_text,
                "end_date": "present",
            })
            idx += 1
            continue

        # A common real-world pattern is: Title on one line, company/location on the next.
        if re.search(r"(?i)\b(?:developer|engineer|analyst|scientist|manager|consultant|specialist|lead|director)\b", line):
            title = line
            company = ""
            location = ""
            responsibilities = []
            for next_index in range(idx + 1, min(len(lines), idx + 5)):
                candidate = lines[next_index].strip()
                if not candidate or section_end_pattern.match(candidate):
                    continue
                if date_pattern.search(candidate):
                    break
                if not company:
                    company = candidate
                    continue
                if not location and re.search(r"\b(?:ny|ca|tx|fl|wa|ga|ma|il|co|india|usa|uk|germany|bengal|kolkata|new york|albany|buffalo)\b", candidate, re.IGNORECASE):
                    location = candidate
                    continue
                responsibilities.append(candidate)
            if company or responsibilities:
                entries.append({
                    "company": company,
                    "job_title": title,
                    "location": location,
                    "responsibilities": responsibilities,
                    "technologies": [],
                    "additional_information": [],
                })
        idx += 1

    if entries:
        return entries

    # Last-resort fallback based on a date-bearing line and the nearby context.
    for index, line in enumerate(lines):
        if not date_pattern.search(line):
            continue
        title = ""
        for prev_index in range(index - 1, max(-1, index - 5), -1):
            candidate = lines[prev_index].strip()
            if candidate and not date_pattern.search(candidate) and not section_end_pattern.match(candidate):
                title = candidate
                break
        company = ""
        for next_index in range(index + 1, min(len(lines), index + 5)):
            candidate = lines[next_index].strip()
            if candidate and not date_pattern.search(candidate) and not section_end_pattern.match(candidate):
                company = candidate
                break
        if not title and not company:
            continue
        entries.append({
            "company": company,
            "job_title": title,
            "location": "",
            "responsibilities": [],
            "technologies": [],
            "additional_information": [line],
        })
    return entries


def calculate_years_of_experience(experiences: list[dict]) -> float:
    """Aggregate the date ranges in the extracted experience entries."""
    if not experiences:
        return 0.0

    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }

    def parse_date(value: str):
        if not value:
            return None
        value = value.strip()
        if value.lower() in {"present", "current"}:
            return (2026, 9)
        match = re.search(r"(?i)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|(?:19|20)\d{2})", value)
        if not match:
            year_match = re.search(r"(?:19|20)\d{2}", value)
            if not year_match:
                return None
            return (int(year_match.group(0)), 1)
        month_token = match.group(0)
        month_key = month_token.lower()
        year_match = re.search(r"(?:19|20)\d{2}", value)
        year = int(year_match.group(0)) if year_match else 2000
        month = month_map.get(month_key, 1)
        return (year, month)

    total_months = 0
    for experience in experiences:
        start_value = experience.get("start_date") or experience.get("start_year") or experience.get("start")
        end_value = experience.get("end_date") or experience.get("end_year") or "present"
        if not start_value:
            continue
        start = parse_date(str(start_value))
        end = parse_date(str(end_value))
        if not start or not end:
            continue
        total_months += (end[0] - start[0]) * 12 + (end[1] - start[1])

    return round(total_months / 12, 1) if total_months else 0.0


def extract_education_entries(text: str) -> list[dict[str, str]]:
    """Extract degree, institution, and year information from education sections."""
    if not text or not text.strip():
        return []

    lines = [line.strip(" -*•\t") for line in text.splitlines()]
    section_heading_pattern = re.compile(r"(?i)^(?:education|academic background|educational background|qualifications)\s*:??\s*$")
    section_end_pattern = re.compile(r"(?i)^(?:experience|work experience|professional experience|skills|technical skills|projects|certifications|languages known|hobbies)\s*:??\s*$")

    degree_keywords = (
        "b.tech", "m.tech", "b.e", "m.e", "bachelor", "master", "phd",
        "doctorate", "diploma", "secondary", "senior secondary", "high school"
    )

    start_index = None
    for idx, line in enumerate(lines):
        if section_heading_pattern.match(line):
            start_index = idx + 1
            break

    if start_index is None:
        start_index = 0

    entries = []
    idx = start_index
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if section_end_pattern.match(line):
            break
        if any(keyword in line.lower() for keyword in degree_keywords):
            degree = line
            institution = ""
            location = ""
            start_year = ""
            end_year = ""
            seen_years = []
            j = idx + 1
            while j < len(lines) and j < idx + 8:
                candidate = lines[j].strip()
                if not candidate or section_end_pattern.match(candidate):
                    break
                if re.search(r"\b(?:19|20)\d{2}\b", candidate):
                    years = re.findall(r"\b(?:19|20)\d{2}\b", candidate)
                    seen_years.extend(years)
                    j += 1
                    continue
                if re.search(r"\d+(?:\.\d+)?\s*(?:%|\(current\)|current)", candidate, re.IGNORECASE):
                    j += 1
                    continue
                if not institution:
                    institution = candidate
                elif not location:
                    location = candidate
                j += 1
            if seen_years:
                end_year = seen_years[-1]
                if len(seen_years) > 1:
                    start_year = seen_years[0]
            if not start_year and not end_year:
                block = " ".join(lines[idx + 1:j])
                matched_years = re.findall(r"\b(?:19|20)\d{2}\b", block)
                if len(matched_years) >= 2:
                    start_year, end_year = matched_years[0], matched_years[-1]
                elif len(matched_years) == 1:
                    end_year = matched_years[0]
            entries.append({
                "degree": degree,
                "institution": institution,
                "location": location,
                "start_year": start_year,
                "end_year": end_year,
            })
            idx += 1
            continue
        idx += 1

    if entries:
        return entries

    # Generic fallback for degree lines that appear in flat CV text.
    for idx, line in enumerate(lines):
        if not any(keyword in line.lower() for keyword in degree_keywords):
            continue
        degree = line
        institution = ""
        location = ""
        end_year = ""
        for candidate in lines[idx + 1:idx + 6]:
            candidate = candidate.strip()
            if not candidate:
                continue
            if re.search(r"\b(?:19|20)\d{2}\b", candidate):
                end_year = re.findall(r"\b(?:19|20)\d{2}\b", candidate)[-1]
                continue
            if not institution:
                institution = candidate
            elif not location:
                location = candidate
        entries.append({
            "degree": degree,
            "institution": institution,
            "location": location,
            "start_year": "",
            "end_year": end_year,
        })
    return entries


def extract_project_entries(text: str) -> list[dict[str, object]]:
    """Extract project headings and descriptions when a projects section exists."""
    section_match = re.search(
        r"(?im)^\s*(?:projects|personal projects|academic projects|key projects)\s*:?\s*$",
        text,
    )
    if not section_match:
        return []
    project_text = re.split(
        r"(?im)^\s*(?:education|experience|work experience|technical skills|"
        r"skills|certifications|languages known|hobbies)\s*:?\s*$",
        text[section_match.end():],
        maxsplit=1,
    )[0]
    lines = [line.strip(" -*•\t") for line in project_text.splitlines() if line.strip()]
    if not lines:
        return []
    entries = []
    current = {"name": lines[0], "description": []}
    for line in lines[1:]:
        if len(line.split()) <= 8 and not line.endswith((".", ";")):
            entries.append(
                {"name": current["name"], "description": "\n".join(current["description"])}
            )
            current = {"name": line, "description": []}
        else:
            current["description"].append(line)
    entries.append(
        {"name": current["name"], "description": "\n".join(current["description"])}
    )
    return entries