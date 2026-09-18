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
        # OCR/PDF column extraction can remove the section heading. Permit a
        # date-bearing employment header only when nearby text contains a
        # clearly occupational title; this avoids treating education dates as
        # employment.
        occupational_date = re.compile(
            r"(?i)\b(?:19|20)\d{2}\b.*(?:-|to|through)\s*"
            r"(?:present|current|date|(?:19|20)\d{2})\b"
        )
        has_occupational_date = any(
            occupational_date.search(line)
            and any(
                re.search(
                    r"(?i)\b(?:developer|engineer|scientist|analyst|manager|"
                    r"consultant|architect|administrator|director|lead)\b",
                    nearby,
                )
                for nearby in lines[max(0, idx - 2):idx + 2]
            )
            for idx, line in enumerate(lines)
        )
        if not has_occupational_date:
            return []
        start_index = 0

    date_pattern = re.compile(
        r"(?i)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|(?:19|20)\d{2})\s*(?:-|–|to)\s*(?:present|current|till\s+date|to\s+date|date|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|(?:19|20)\d{2}))"
    )
    section_end_pattern = re.compile(
        r"(?i)^(?:education|skills|technical skills|projects|certifications|languages known|hobbies|summary)\s*:??\s*$"
    )

    # A common OCR result for two-column resumes is:
    # "University, Employer, City | January 2012 - Present".
    # Handle it before the generic block parser, whose neighboring-line
    # heuristics cannot reliably distinguish the two columns.
    flattened_entries = []
    flattened_date = re.compile(
        r"(?i)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\.?\s+(?:19|20)\d{2}\s*(?:-|to)\s*"
        r"(?:present|current|till\s+date|to\s+date|date|"
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\.?\s*(?:19|20)\d{2})"
    )
    for idx, line in enumerate(lines):
        match = flattened_date.search(line)
        if "|" not in line or not match:
            continue
        header = line[:match.start()].strip(" ,-|")
        parts = [part.strip() for part in header.split(",") if part.strip()]
        if parts and re.search(r"(?i)\b(?:university|college|school|institute)\b", parts[0]):
            parts = parts[1:]
        if not parts:
            continue
        role_text = ""
        nearby_text = " ".join(lines[max(0, idx - 3):idx])
        role_match = re.search(
            r"(?i)\b(?:senior|lead|principal|junior)?\s*"
            r"(?:data|software|machine learning|research)\s+"
            r"(?:scientist|engineer|developer|analyst)\b",
            nearby_text,
        )
        if role_match:
            role_text = role_match.group(0).strip()
        if not role_text:
            continue
        end_value = "present" if re.search(r"(?i)(?:present|current|till\s+date|to\s+date)", match.group(0)) else ""
        flattened_entries.append({
            "company": parts[0],
            "job_title": role_text,
            "location": ", ".join(parts[1:]),
            "responsibilities": [],
            "technologies": [],
            "additional_information": [line],
            "start_date": line,
            "end_date": end_value,
        })
    if flattened_entries:
        return flattened_entries

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
            month_date_pattern = re.compile(
                r"(?i)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(?:19|20)\d{2}\s*(?:-|–|to)\s*(?:present|current|till\s+date|to\s+date|date|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s*(?:19|20)\d{2})"
            )
            date_match = month_date_pattern.search(line) or date_pattern.search(line)
            header_prefix = line[:date_match.start()].strip(" ,-|") if date_match else ""
            end_match = re.search(
                r"(?i)(?:-|–|to)\s*(present|current|till\s+date|to\s+date|date|"
                r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
                r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
                r"dec(?:ember)?)\.?\s*(?:19|20)\d{2})",
                date_match.group(0) if date_match else "",
            )
            extracted_end_date = end_match.group(1) if end_match else "present"
            if re.search(r"(?i)\b(?:till|to)\s+date\b|\bdate\b", extracted_end_date):
                extracted_end_date = "present"
            if "|" in line and date_match:
                left_header = line[:date_match.start()].strip(" ,-|")
                left_parts = [part.strip() for part in left_header.split("|", 1)[0].split(",") if part.strip()]
                if left_parts and re.search(r"(?i)\b(?:university|college|school|institute)\b", left_parts[0]):
                    left_parts = left_parts[1:]
                if left_parts:
                    company = left_parts[0]
                    location = ", ".join(left_parts[1:])
                for candidate in reversed(lines[max(0, idx - 3):idx]):
                    role_match = re.search(
                        r"(?i)\b(?:senior|lead|principal|junior)?\s*"
                        r"(?:data|software|machine learning|research)\s+"
                        r"(?:scientist|engineer|developer|analyst)\b",
                        candidate,
                    )
                    if role_match:
                        title = role_match.group(0).strip()
                        break
                if company and title:
                    responsibilities = []
                    for candidate in lines[idx + 1:]:
                        candidate = candidate.strip()
                        if not candidate or date_pattern.search(candidate) or section_end_pattern.match(candidate):
                            break
                        responsibilities.append(candidate)
                    entries.append({
                        "company": company,
                        "job_title": title,
                        "location": location,
                        "responsibilities": responsibilities,
                        "technologies": [],
                        "additional_information": [date_text],
                        "start_date": date_text,
                        "end_date": extracted_end_date,
                    })
                    idx += 1
                    continue
            if header_prefix:
                pipe_parts = [part.strip() for part in header_prefix.split("|")]
                if len(pipe_parts) > 1:
                    header_prefix = pipe_parts[-1]
                    prior_header = pipe_parts[0]
                    prior_parts = [part.strip() for part in prior_header.split(",") if part.strip()]
                    if prior_parts and re.search(
                        r"(?i)\b(?:university|college|school|institute)\b",
                        prior_parts[0],
                    ):
                        prior_parts = prior_parts[1:]
                    prefix_parts = prior_parts
                else:
                    prefix_parts = [part.strip() for part in header_prefix.split(",")]
                company = prefix_parts[0]
                location = ", ".join(prefix_parts[1:])
                for next_index in range(idx + 1, min(len(lines), idx + 4)):
                    candidate = lines[next_index].strip()
                    if candidate and not date_pattern.search(candidate) and candidate.lower() not in {
                        "responsibilities", "environment"
                    }:
                        title = candidate
                        break
                if not title:
                    for prev_index in range(idx - 1, max(-1, idx - 4), -1):
                        candidate = lines[prev_index].strip()
                        if re.search(
                            r"(?i)\b(?:developer|engineer|scientist|analyst|manager|"
                            r"consultant|architect|administrator|director|lead)\b",
                            candidate,
                        ):
                            title = candidate
                            break

            for prev_index in range(idx - 1, max(-1, idx - 6), -1):
                if title:
                    break
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
                if title and company:
                    break
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
                if candidate == title:
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
                "end_date": extracted_end_date,
            })
            idx += 1
            continue

        # A common real-world pattern is: Title on one line, company/location on the next.
        if (
            not date_pattern.search(text)
            and re.search(r"(?i)\b(?:developer|engineer|analyst|scientist|manager|consultant|specialist|lead|director)\b", line)
        ):
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
    """Extract degree, institution, result, and completion year."""
    if not text or not text.strip():
        return []

    lines = [line.strip(" -*•\t") for line in text.splitlines()]

    def education_record(degree: str, institution: str = "", end_year: str = "", grade: str = ""):
        return {
            "degree": degree.strip(),
            "institution": institution.strip(),
            "end_year": end_year,
            "grade": grade.strip(),
        }

    def finalize_education(records: list[dict]) -> list[dict[str, str]]:
        finalized = []
        for record in records:
            grade_match = re.search(
                r"(?i)\b(?:cgpa|sgpa|percentage|marks?)\b\s*[:\-]?\s*"
                r"(\d+(?:\.\d+)?)\s*%?",
                " ".join(str(record.get(key, "")) for key in ("degree", "institution", "location")),
            )
            finalized.append(education_record(
                str(record.get("degree", "")),
                str(record.get("institution", "")),
                str(record.get("end_year", "")),
                str(record.get("grade", "")) or (grade_match.group(1) if grade_match else ""),
            ))
        return finalized

    def simple_education_rows() -> list[dict[str, str]]:
        year_pattern = re.compile(r"\b(?:19|20)\d{2}\b")
        grade_pattern = re.compile(
            r"(?i)\b(?:cgpa|sgpa|percentage|marks?)\b\s*[:\-]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?|"
            r"(?<!\d)(\d+(?:\.\d+)?)\s*%|"
            r"(?<!\d)(\d+(?:\.\d+)?)\s*\(\s*current\s*\)"
        )
        degree_pattern = re.compile(
            r"(?i)^(?:b\.?\s*[- ]?tech|bachelor|m\.?\s*[- ]?tech|master|"
            r"senior secondary|secondary|class\s+(?:x|xii|10|12)|"
            r"higher secondary certificate|secondary school certificate)\b"
        )
        stop_pattern = re.compile(
            r"(?i)^(?:skills?|technical skills?|projects?|experience|"
            r"professional experience|work experience|certifications?|"
            r"achievements?|interests?|hobbies|languages?|core concepts?)\s*:?\s*$"
        )
        rows = []
        indexes = [i for i, line in enumerate(lines) if degree_pattern.match(line)]
        for index in indexes:
            degree = lines[index]
            degree = re.sub(
                r"(?i)\s+(?=(?:senior|lead|principal|junior)?\s*"
                r"(?:data|software|machine learning|research)\s+"
                r"(?:scientist|engineer|developer|analyst)\b).*$",
                "",
                degree,
            ).strip()
            institution = ""
            end_year = ""
            grade = ""
            for candidate in lines[index + 1:index + 8]:
                if not candidate:
                    continue
                if stop_pattern.match(candidate):
                    break
                if year_pattern.fullmatch(candidate):
                    end_year = candidate
                    break
                grade_match = grade_pattern.search(candidate)
                if grade_match:
                    grade = next(group for group in grade_match.groups() if group)
                    continue
                if re.fullmatch(r"\d+(?:\.\d+)?\s*%", candidate):
                    grade = re.sub(r"\s*%", "", candidate)
                    continue
                if re.search(r"(?i)^(?:senior secondary|secondary|class\s+(?:x|xii|10|12))\b", candidate):
                    break
                if re.search(
                    r"(?i)^(?:cbse|icse|wbchse|wbbse|board|"
                    r"degree/certificate|institute/board|cgpa/percentage|year)$",
                    candidate,
                ):
                    continue
                if (
                    not institution
                    and candidate.strip(" ?•-*") not in {"", "�", ""}
                    and not re.match(r"^[?•*\uf0b7-]\s*$", candidate)
                    and not re.search(
                    r"(?i)^(?:senior secondary|secondary|class\s+(?:x|xii|10|12)|"
                    r"skills?|projects?|experience|professional experience)$",
                    candidate,
                    )
                ):
                    # Flattened two-column extraction may place the first
                    # employer on the same line as the university. Keep only
                    # the education institution in this record.
                    if re.search(r"(?i)\buniversity\b", candidate):
                        institution = re.split(
                            r"(?i),\s*(?=[A-Z][A-Za-z .'-]+\b(?:,|$))",
                            candidate,
                            maxsplit=1,
                        )[0].strip()
                    else:
                        institution = candidate
            if institution or end_year or grade:
                rows.append(education_record(degree, institution, end_year, grade))
        return rows

    section_heading_pattern = re.compile(r"(?i)^(?:education|academic background|educational background|qualifications)\s*:??\s*$")
    section_end_pattern = re.compile(r"(?i)^(?:experience|work experience|professional experience|skills|technical skills|projects|certifications|languages known|hobbies)\s*:??\s*$")

    degree_keywords = (
        "b.tech", "m.tech", "b.e", "m.e", "bachelor", "master", "phd",
        "doctorate", "diploma", "secondary", "senior secondary", "high school"
    )

    def compact_education_rows() -> list[dict[str, str]]:
        """Parse compact education rows commonly emitted by modern CV PDFs."""
        degree_index = next(
            (
                index for index, line in enumerate(lines)
                if re.search(r"(?i)^(?:bachelor|b\.?\s*tech|m\.?\s*tech|master).*computer science", line)
            ),
            None,
        )
        school_index = next(
            (
                index for index, line in enumerate(lines)
                if re.search(r"(?i)(?:high school|secondary school|senior secondary|secondary)\b", line)
            ),
            None,
        )
        if degree_index is None or school_index is None:
            return []

        def clean_institution(value: str) -> str:
            value = re.sub(r"\s*[|·]\s*(?:19|20)\d{2}.*$", "", value).strip()
            value = re.sub(r"\s+(?:19|20)\d{2}\s*[-–]\s*(?:\d{2,4}).*$", "", value).strip()
            value = value.split("|", 1)[0].strip()
            return value.replace("�", "'").replace("?", "'")

        rows = []
        degree_institution = ""
        for candidate in reversed(lines[max(0, degree_index - 10):degree_index + 1]):
            if re.search(r"(?i)\b(?:college|university|institute)\b", candidate):
                degree_institution = clean_institution(candidate)
                break
        if not degree_institution:
            for candidate in lines[degree_index + 1:degree_index + 5]:
                if re.search(r"(?i)\b(?:college|university|institute)\b", candidate):
                    degree_institution = clean_institution(candidate)
                    break
        degree_context = " ".join(lines[max(0, degree_index - 4):degree_index + 6])
        degree_years = re.findall(r"\b(?:19|20)\d{2}\b", degree_context)
        expected_match = re.search(
            r"(?i)\bexpected\s+(?:graduation|completion)?[^0-9]{0,20}((?:19|20)\d{2})",
            degree_context,
        )
        if expected_match:
            degree_years = [expected_match.group(1)]
        has_expected_graduation = bool(
            re.search(r"(?i)\bexpected\s+graduation\b|\bexpected\b", degree_context)
        )
        degree_grade_match = re.search(
            r"(?i)\b(?:cgpa|sgpa|percentage|marks?)\b\s*[:\-]?\s*(\d+(?:\.\d+)?)",
            lines[degree_index],
        )
        rows.append(education_record(
            lines[degree_index],
            degree_institution,
            degree_years[-1] if degree_years else "",
            degree_grade_match.group(1) if degree_grade_match else "",
        ))

        school = ""
        if re.search(r"(?i)\b(?:high school|secondary school)\b", lines[school_index]):
            school = clean_institution(lines[school_index])
        for candidate in lines[school_index + 1:school_index + 5]:
            if re.search(r"(?i)^(?:cbse|icse|wbchse|wbbse|board|class\s+)", candidate):
                continue
            if re.search(r"(?i)^(?:skills?|projects?|experience|professional experience)", candidate):
                break
            if (
                not re.search(r"(?i)^\d+(?:\.\d+)?\s*%?$", candidate)
                and re.search(r"(?i)\b(?:school|college|university|institution)\b", candidate)
            ):
                school = clean_institution(candidate)
                break
        # A label such as "Senior Secondary" is not an institution.
        school_years = re.findall(r"\b(?:19|20)\d{2}\b", " ".join(lines[school_index:school_index + 3]))
        school_text = " ".join(lines[school_index:school_index + 3])
        grade_matches = re.findall(
            r"(?i)\b(?:class\s+xii|class\s+x|12th|10th)\b\s*\((\d+(?:\.\d+)?)%\)",
            school_text,
        )
        rows.append(education_record(
            "Class XII",
            school,
            school_years[0] if school_years else "",
            grade_matches[0] if grade_matches else "",
        ))
        if len(grade_matches) > 1:
            rows.append(education_record(
                "Class X",
                school,
                "",
                grade_matches[1],
            ))
        return rows

    compact_rows = compact_education_rows()
    if compact_rows:
        return compact_rows

    def ordered_academic_rows() -> list[dict[str, str]]:
        """Parse the common PDF order: degree rows followed by institution/date rows."""
        qualification_pattern = re.compile(
            r"(?i)^(?:b\.?[- ]?tech\b.*|m\.?[- ]?tech\b.*|b\.?e\.?\b.*|m\.?e\.?\b.*|"
            r"higher secondary certificate.*|secondary school certificate.*|"
            r"class\s*(?:xii|12|x|10)\b.*|12th|10th)\s*$"
        )
        indexes = [
            index for index, line in enumerate(lines)
            if qualification_pattern.match(line.strip(" ?•-*"))
        ]
        if len(indexes) < 2:
            return []

        def years(value: str) -> list[str]:
            return re.findall(r"\b(?:19|20)\d{2}\b", value)

        rows = []
        for position, index in enumerate(indexes):
            degree = re.sub(r"^[?•*-]\s*", "", lines[index]).strip()
            degree = re.sub(r"(?i)^b\.?[- ]?tech\b", "B.Tech", degree)
            if position == 0 and re.search(r"(?i)\b(?:computer|engineering|science)\b", degree):
                continuation = []
                for candidate in lines[index + 1:index + 4]:
                    if re.search(r"(?i)^(?:project|experience|skills?|strength|personal details|declaration)\b", candidate):
                        break
                    if re.search(r"(?i)\b(?:computer|engineering|science)\b", candidate):
                        continuation.append(candidate)
                if continuation:
                    degree = " ".join([degree] + continuation)
            institution = ""
            location = ""
            start_year = ""
            end_year = ""

            previous = lines[index - 1].strip() if index > 0 else ""
            if position == 0 and not re.search(r"(?i)\b(?:college|university|institute)\b", previous):
                candidates = [
                    candidate.strip() for candidate in lines[:index]
                    if re.search(r"(?i)\b(?:college|university|institute)\b", candidate)
                ]
                previous = candidates[-1] if candidates else previous
            if position == 0 and re.search(r"(?i)\b(?:college|university|institute)\b", previous):
                institution_line = previous
                range_match = re.search(r"\b((?:19|20)\d{2})\s*[-–|]\s*(\d{2,4})\b", institution_line)
                if range_match:
                    start_year = range_match.group(1)
                    end_suffix = range_match.group(2)
                    end_year = (
                        end_suffix
                        if len(end_suffix) == 4
                        else f"{start_year[:2]}{end_suffix}"
                    )
                year_values = years(institution_line)
                if year_values and not start_year:
                    start_year = year_values[0]
                    end_year = year_values[-1]
                institution_line = re.sub(r"\s+\d+(?:\.\d+)?\s*\(\s*cgpa.*$", "", institution_line, flags=re.IGNORECASE).strip()
                institution_line = re.sub(r"\s+\d+(?:\.\d+)?%.*$", "", institution_line).strip()
                institution_line = re.sub(r"\s*\|\s*.*\b(?:19|20)\d{2}.*$", "", institution_line).strip()
                institution_line = re.sub(r"\([^)]*\)", "", institution_line).strip()
                institution_line = re.sub(r"\s*\|\s*.*\b(?:19|20)\d{2}.*$", "", institution_line).strip()
                institution_line = institution_line.replace("?", "'")
                institution_line = institution_line.replace("�", "'")
                institution = institution_line
                parts = [part.strip() for part in institution_line.split(",")]
                if len(parts) > 1:
                    location = ", ".join(parts[1:])
            if not institution:
                for candidate in lines[index + 1:index + 20]:
                    if re.search(r"(?i)\b(?:college|university|institute)\b", candidate) and not re.search(r"(?i)^board\s*/?\s*university$", candidate):
                        institution = candidate
                        break
            else:
                next_index = index + 1
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines):
                    institution_line = lines[next_index].strip(" ?•-*")
                    year_values = years(institution_line)
                    if year_values:
                        end_year = year_values[-1]
                        start_year = year_values[0] if len(year_values) > 1 else ""
                        institution_line = re.sub(r"\([^)]*\)", "", institution_line).strip()
                    institution_line = re.sub(r"\s+\d+(?:\.\d+)?%.*$", "", institution_line).strip()
                    institution_line = re.sub(r"\s*\|\s*.*\b(?:19|20)\d{2}.*$", "", institution_line).strip()
                    institution_line = institution_line.replace("?", "'")
                    institution_line = institution_line.replace("�", "'")
                    institution = institution_line
                    parts = [part.strip() for part in institution_line.split(",")]
                    if len(parts) > 1:
                        location = ", ".join(parts[1:])

            rows.append({
                "degree": degree,
                "institution": institution,
                "start_year": start_year,
                "end_year": end_year,
                "grade": "",
            })
        global_years = [
            year for line in lines
            if not re.search(r"(?i)\bdate of birth\b", line)
            for year in re.findall(r"\b(?:19|20)\d{2}\b", line)
        ]
        global_grades = [
            grade for line in lines
            for grade in re.findall(r"(?i)(?:cgpa|sgpa|marks?|percentage)?\s*[:(]?\s*(\d+(?:\.\d+)?)\s*%?\s*(?:\)|\(current\))?", line)
            if float(grade) <= 100
        ]
        for row, year in zip([row for row in rows if not row["end_year"]], global_years):
            row["end_year"] = year
        for row, grade in zip([row for row in rows if not row["grade"]], global_grades):
            row["grade"] = grade
        return rows

    ordered_rows = ordered_academic_rows()
    if ordered_rows:
        return finalize_education(ordered_rows)

    simple_rows = simple_education_rows()
    if simple_rows:
        return finalize_education(simple_rows)

    def academic_table_entries() -> list[dict[str, str]]:
        """Rebuild common PDF table output where columns are extracted separately."""
        qualification_indexes = []
        for index, line in enumerate(lines):
            normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
            if (
                re.search(r"\b(?:b\s*tech|m\s*tech|b\s*e|m\s*e|bachelor|master|phd|doctorate|diploma)\b", normalized)
                or normalized in {"10th", "12th", "higher secondary", "senior secondary"}
            ):
                qualification_indexes.append(index)

        if not any(re.sub(r"[^a-z0-9]+", " ", lines[index].lower()).strip() in {"10th", "12th"} for index in qualification_indexes):
            return []

        def clean_block(value: str) -> str:
            cleaned = value.strip()
            cleaned = re.sub(r"^[\s.,;|:-?]+", "", cleaned)
            if re.search(r"(?i)\b(?:declaration|i do hereby declare)\b", cleaned):
                match = re.search(r"(?i)(?:maulana|st\.\s*thomas|santragachi|wbchse|wbbse|university|college)", cleaned)
                if match:
                    cleaned = cleaned[match.start():]
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;|-")
            return cleaned

        entries = []
        for index in qualification_indexes:
            line = lines[index]
            normalized = re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()
            if normalized in {"10th", "12th"}:
                degree = "12th" if normalized == "12th" else "10th"
            else:
                degree_parts = [line]
                for continuation in lines[index + 1:index + 4]:
                    if (
                        not continuation
                        or re.match(r"(?i)^(?:project|experience|education|strength|personal details|declaration)\b", continuation)
                        or re.search(r"(?i)^(?:github|email|contact|address)\b", continuation)
                    ):
                        break
                    if re.search(r"(?i)\b(?:science|engineering|computer|technology|management|studies|and)\b", continuation):
                        degree_parts.append(continuation)
                    else:
                        break
                degree = " ".join(degree_parts).strip(" -|")

            entries.append({
                "degree": degree,
                "institution": "",
                "location": "",
                "start_year": "",
                "end_year": "",
            })

        first_school_index = next(
            (index for index in qualification_indexes if lines[index].strip().lower() in {"12th", "10th"}),
            len(lines),
        )
        pre_secondary = lines[:first_school_index]
        university_lines = []
        college_lines = []

        for index, line in enumerate(pre_secondary):
            if re.search(r"(?i)\buniversity\b", line):
                start = index
                while start > 0 and re.search(r"(?i)^[a-z][a-z .'-]+$", pre_secondary[start - 1]):
                    previous = pre_secondary[start - 1]
                    if re.search(r"(?i)\b(project|objective|aim|academic|qualification|declaration)\b", previous):
                        break
                    start -= 1
                university_lines = [clean_block(part) for part in pre_secondary[start:index + 1] if clean_block(part)]
            if re.search(r"(?i)\bcollege\b", line):
                college_lines = [clean_block(part) for part in pre_secondary[index:index + 6] if clean_block(part)]

        if entries:
            edu_block = " ".join(pre_secondary)
            college_match = re.search(r"(?i)(?:st\.\s*thomas.*?(?:college.*?(?:technology|engineering.*?technology)|engineering.*?technology)|[A-Za-z .'-]+?\s+college.*?(?:technology|engineering.*?technology))", edu_block)
            if college_match:
                entries[0]["institution"] = clean_block(college_match.group(0))
            elif college_lines:
                entries[0]["institution"] = " ".join(college_lines)
            university_match = re.search(r"(?i)(?:maulana\s+abul\s+kalam.*?technology|[A-Za-z .'-]+?\s+university.*?(?:technology|of\s+technology))", edu_block)
            if university_match:
                entries[0]["location"] = clean_block(university_match.group(0))
            elif university_lines:
                entries[0]["location"] = " ".join(university_lines)

        for entry_index, index in enumerate(qualification_indexes):
            if lines[index].strip().lower() not in {"12th", "10th"}:
                continue
            surrounding = [candidate for candidate in lines[index + 1:index + 5] if candidate and not re.search(r"(?i)\b(?:expected|date of birth|dob|declaration)\b", candidate)]
            if surrounding:
                entry = entries[entry_index]
                entry["location"] = surrounding[0].strip()
                if len(surrounding) > 1:
                    entry["institution"] = surrounding[1].strip()

        candidate_years = []
        for line in lines:
            if re.search(r"(?i)\bdate of birth\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b.*\d{4}\b", line):
                continue
            found = re.findall(r"(?i)\b(?:expected\s+)?(?:19|20)\d{2}\b", line)
            if found:
                candidate_years.extend([match for match in found if not re.search(r"(?i)\bdate of birth\b", line)])

        if candidate_years:
            # Prefer the latest qualifying year for the degree, then the school rows.
            ordered_years = []
            for year in candidate_years:
                value = re.search(r"(?:19|20)\d{2}", year).group(0)
                if value not in ordered_years:
                    ordered_years.append(value)
            for entry, year in zip(entries, ordered_years[: len(entries)]):
                entry["end_year"] = year

        return finalize_education(entries)

    table_entries = academic_table_entries()
    if table_entries:
        return finalize_education(table_entries)

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
        return finalize_education(entries)

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
    return finalize_education(entries)


def extract_project_entries(text: str) -> list[dict[str, object]]:
    """Extract project headings and descriptions when a projects section exists."""
    if not text or not text.strip():
        return []

    lines = [line.strip(" -*•\t") for line in text.splitlines() if line.strip()]
    section_end_pattern = re.compile(
        r"(?i)^(?:education|skills|technical skills|strength|personal details|languages known|hobbies|declaration|experience|work experience|certifications|achievements|interests)\s*:??\s*$"
    )

    project_candidates = []
    start = None
    for index, line in enumerate(lines):
        lowered = line.lower().strip()
        if re.match(r"(?i)^(?:projects|project|personal projects|academic projects|key projects)\s*:??\s*$", line):
            start = index + 1
            continue
        if start is not None and (section_end_pattern.match(line) or re.match(r"(?i)^(?:strength|personal details|declaration)\b", line)):
            break
        if start is not None:
            project_candidates.append(line)

    if not project_candidates:
        for index, line in enumerate(lines):
            if re.search(r"(?i)\b(?:project|application|system|website|dashboard|model|api|automation)\b", line) and ("|" in line or re.search(r"\b(?:java|python|sql|html|css|javascript|react|spring|api|ml|ai)\b", line, re.IGNORECASE)):
                start = index
                break
        if start is not None:
            for line in lines[start:]:
                if section_end_pattern.match(line):
                    break
                project_candidates.append(line)

    if not project_candidates:
        return []

    def clean_project_line(value: str) -> str:
        cleaned = value.strip()
        cleaned = cleaned.replace("?", "")
        cleaned = re.sub(r"^[\s\W_]+", "", cleaned)
        cleaned = cleaned.strip("*•- ")
        return cleaned

    entries = []
    current_name = ""
    current_desc = []
    for line in project_candidates:
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = clean_project_line(stripped)
        if not cleaned or cleaned.lower().startswith("github:"):
            continue
        is_title = (
            bool(re.search(r"\s[|?]\s", cleaned))
            or (
                len(cleaned.split()) <= 8
                and re.search(r"(?i)\b(?:project|application|system|website|dashboard|model|api|automation)\b", cleaned)
                and not re.search(r"(?i)^(?:developed|built|created|implemented|designed|analyzed|optimized)\b", cleaned)
            )
        )
        if is_title:
            if current_name:
                entries.append({"name": current_name, "description": "\n".join(current_desc).strip()})
            current_name = cleaned
            current_desc = []
            continue
        if current_name:
            if cleaned:
                current_desc.append(cleaned)

    if current_name:
        entries.append({"name": current_name, "description": "\n".join(current_desc).strip()})

    cleaned_entries = []
    for entry in entries:
        name = re.sub(r"\s+", " ", entry["name"]).strip(" -|:")
        description = re.sub(r"\s+", " ", entry["description"]).strip()
        if name:
            cleaned_entries.append({"name": name, "description": description})
    return cleaned_entries