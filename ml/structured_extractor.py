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