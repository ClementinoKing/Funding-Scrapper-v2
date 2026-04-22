import os
import json
import re
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class AIEnhancer:
    def __init__(self, config: dict):
        self.config = config
        self.ai_provider = config.get("aiProvider") or os.getenv("AI_PROVIDER", "openai")

        if self.ai_provider == "openai":
            self.api_key = config.get("openaiKey") or os.getenv("OPENAI_API_KEY")
        elif self.ai_provider == "groq":
            self.api_key = config.get("groqKey") or os.getenv("GROQ_API_KEY")
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

        if not self.api_key:
            raise ValueError(f"AI API key not found for provider: {self.ai_provider}")

    # -----------------------------
    # Public entrypoint
    # -----------------------------
    async def enhance(self, item: dict, page_text: str):
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(item, page_text)

        if self.ai_provider == "openai":
            return await self._enhance_openai(system_prompt, user_prompt)
        elif self.ai_provider == "groq":
            return await self._enhance_groq(system_prompt, user_prompt)

    # -----------------------------
    # Prompt builders
    # -----------------------------
    def _build_system_prompt(self) -> str:
        return """
You are a deterministic data-processing and normalization engine.

Rules you MUST follow:
- Output MUST be valid JSON only
- No markdown, no commentary, no explanations
- Do NOT infer missing data
- Never hallucinate facts
- Follow the schema EXACTLY
- Use ONLY provided data
- Prefer website content over raw scraped data if conflicts exist
- If information is missing, write "Not specified" or null
- Follow the schema EXACTLY
"""

    def _build_user_prompt(self, item: dict, page_text: str) -> str:
        return f"""
Transform the following raw database record into a clean, human-readable summary and structured insights.

SOURCE URL:
{item.get("url", "Not specified")}

WEBSITE CONTENT:
{page_text or "No website content provided."}

RAW SCRAPED DATA:
{json.dumps(item, indent=2)}

SCHEMA:
"title": string,
"summary": string,
"url": string,
"eligibility": string,
"funding_amount": string,
"deadlines": string,
"contact_email": string | null,
"contact_phone": string | null,
"application_process": string,
"sectors": string,
"slug": string,
"confidence": number (0-1),
"age": string,
"gender": string,
"ethnicity": string,
"desired_location": string,
"program_type": string,
"funding_category": string


Return either a single JSON object or an array of JSON objects if splitting into multiple opportunities.

KEYPOINTS:
- If the program seems to have multiple funding opportunities, let's say there are multiple grants under one umbrella program or a grant and a loan in one program, return an array of separate JSON objects following the schema provided, one for each distinct funding opportunity.
- Once you split the funding opportunities, determine the program type (program_type) as well, if its a grant, loan etc.
- You should also be able to determine the funding categories based on the list provided below. Use the column funding_category.
- Focus on clarity and human readability
- Recreate the title to be clear and human friendly.
- Regenerate the summary so it is clear, concise, and suitable for human readers. Make sure the summary captures the essence of the funding opportunity and it should never be empty or "Not specified".
- Make sure you capture the deadline if it has been provided anywhere in the content.

**Available Funding Categories:**
1. Working capital (cashflow)                        
2. Inventory / stock                                 
3. Equipment / assets                                
4. Business expansion / CAPEX (premises, new branch) 
5. Marketing & sales                                 
6. Payroll / hiring                                  
7. Technology / software                             
8. R&D / product development                         
9. Debt consolidation / refinance                    
10. Supplier / trade finance need                     
11. Other 

ELIGIBILITY (CRITICAL):
- Capturing accurate eligibility criteria is a must no matter what, no blanks needed - write something based on the summary or the website content.
- Eligibility describes WHO is allowed to apply.
- Extract ONLY factual conditions explicitly stated in the content.
- You can also use the raw scraped data for eligibility extraction.
- The summary can also be used to find eligibility information.
- Look for eligibility information using these indicators: /(eligib|requirements|qualif|who can apply|criteria|support|applicants must|open to)/i
- Include conditions such as:
    * organisation type (individuals, SMEs, startups, NGOs, companies, researchers, students)
    * geographic restrictions (country, province, region)
    * legal status (registered entity, tax compliant, licensed)
    * demographic restrictions (age, gender, ethnicity) ONLY if explicitly stated
    * sector or activity restrictions ONLY if framed as eligibility
- EXCLUDE:
    * application steps
    * selection process descriptions
    * evaluation criteria
    * benefits or funding usage
- If eligibility is spread across multiple sections, combine into a single readable paragraph.

- Funding amount must be explicit, include currency, and be human-readable (e.g. "ZAR 50000", "ZAR 10000000", "USD 10000").

- Deadlines must be a clear date ("31 December 2024"), "Open", or "Not specified".

- Extract contact email and phone number if explicitly present; otherwise use null.

APPLICATION PROCESS:
- Summarize HOW to apply.
- Include steps if available, otherwise a short descriptive paragraph.

- Capture sectors clearly; if missing write "Not specified".

AGE:
- Extract age ONLY if explicitly stated.
- Format as a range, e.g. "18-25".
- If missing, write "Not specified".

GENDER:
- Extract gender ONLY if explicitly stated.
- If missing, write "Not specified".

ETHNICITY:
- Extract ethnicity ONLY if explicitly stated.
- If missing, write "Not specified".
"""

    # -----------------------------
    # Providers
    # -----------------------------
    async def _enhance_openai(self, system_prompt: str, user_prompt: str):
        client = OpenAI(api_key=self.api_key)

        model = self.config.get("aiModel", "gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return self._parse_json(content)

    async def _enhance_groq(self, system_prompt: str, user_prompt: str):
        model = self.config.get("aiModel", "llama-3.3-70b-versatile")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )

            if response.status_code != 200:
                raise RuntimeError(f"Groq API error: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return self._parse_json(content)

    # -----------------------------
    # JSON parsing
    # -----------------------------
    def _parse_json(self, content: str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", content)
            if match:
                return json.loads(match.group(0))
            raise ValueError("Failed to parse AI response as JSON")