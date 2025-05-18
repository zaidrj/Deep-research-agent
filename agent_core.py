# --------------------------------------------------------------------------
# agent_core.py: Contains the agent's definition, tools, and core setup.
# --------------------------------------------------------------------------

import os
from datetime import datetime
import pytz
from typing import Dict, Any, List
#from agents import enable_verbose_stdout_logging     #only uncomment when logging is needed


from dotenv import load_dotenv, find_dotenv

try:
    from firecrawl import FirecrawlApp
except ImportError:
    print("Install 'firecrawl' for the deep research tool: uv add firecrawl")
    FirecrawlApp = None

try:
    from agents import Agent, RunConfig, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, handoff
    from agents.tool import function_tool
except ImportError as e:
    print(f"Failed to import necessary components from 'agents': {e}")
    print("Please ensure the 'agents' library is correctly installed and structured.")
   
    Agent = None
    RunConfig = None
    AsyncOpenAI = None
    OpenAIChatCompletionsModel = None
    Runner = None
    function_tool = lambda f: f 


# Load environment variables needed by the agent core (e.g., API keys)
load_dotenv(find_dotenv())

# --------------------------------------------------------------------------
# Step 1: Provider, Step 2: Model, Step 3: Run Configuration 
# --------------------------------------------------------------------------

provider = AsyncOpenAI(
    api_key=os.getenv("GOOGLE_API_KEY"),             
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.0-flash", 
    openai_client=provider,
)

run_config = RunConfig(
    model=model,
    model_provider=provider,
    tracing_disabled=True # Keep original config
)



# --------------------------------------------------------------------------
# logging
# --------------------------------------------------------------------------

# enable_verbose_stdout_logging()                   #only uncomment when logging is needed also uncomment path at the top!  


# --------------------------------------------------------------------------
# Tool Definitions
# --------------------------------------------------------------------------

@function_tool
async def research_topic(
    query: str,
    max_depth: int,
    time_limit: int,
    max_urls: int
) -> Dict[str, Any]:
    """
    Web-search via FireCrawl API for the latest, authentic sources.**Immediately retry** if the retrieved data timestamp is older than the current timestamp.
    Perform a quick web search for a given topic, returning latest information and summaries from a few top results.
    Use this for general questions or when a brief overview is needed. Do NOT use for deep analysis or synthesis.
    Requires parameters: query (str), max_depth (int, e.g., 5), time_limit (int, seconds, e.g., 180), max_urls (int, e.g., 10). Always use max_depth=5, time_limit=180, max_urls=10 unless the user specifies different numbers.
    """
    if FirecrawlApp is None:
        print("ERROR: firecrawl-python library is required for deep_research but not installed.")
        return {"error": "Deep research tool dependency missing.", "success": False}

    try:
        fc_api_key = os.getenv("FireCrawl_API_KEY")
        if not fc_api_key:
             print("ERROR: FireCrawl_API_KEY environment variable not set.")
             return {"error": "FireCrawl API key not configured.", "success": False}

        firecrawl_app = FirecrawlApp(api_key=fc_api_key)

        results = firecrawl_app.deep_research(
        query= query,
        max_depth=5,
        time_limit=180,
        max_urls=10,
        )

        return {
            "success": True,
            "final_analysis": results.get("data", {}).get("finalAnalysis", "No analysis found."),
            "sources_count": len(results.get("data", {}).get("sources", [])),
            "sources": results.get("data", {}).get("sources", [])
        }

    except Exception as e:
        print(f"ERROR: Deep research tool execution failed for '{query}': {e}")
        return {"error": str(e), "success": False, "final_analysis": "Deep research failed.", "sources_count": 0, "sources": []}



@function_tool
async def deep_research(
    query: str,
    max_depth: int,
    time_limit: int,
    max_urls: int
) -> Dict[str, Any]:
    """
    Web-search via FireCrawl API for the latest, authentic sources.**Immediately retry** if the retrieved data timestamp is older than the current timestamp.Web-search via FireCrawl API for the latest, authentic sources.**Immediately retry** if the retrieved data timestamp is older than the current timestamp.
    Perform comprehensive, in-depth web research on a query using multiple latest sources and providing a synthesized analysis.
    Use this when you need to get the most **up-to-date information, especially concerning events or data from 2025 onwards**, which might not be in your training data.
    Requires parameters: query (str), max_depth (int, e.g., 10), time_limit (int, seconds, e.g., 300), max_urls (int, e.g., 50). Always use max_depth=10, time_limit=300, max_urls=50 unless the user specifies different numbers.
    """
    if FirecrawlApp is None:
        print("ERROR: firecrawl-python library is required for deep_research but not installed.")
        return {"error": "Deep research tool dependency missing.", "success": False}

    try:
        fc_api_key = os.getenv("FireCrawl_API_KEY")
        if not fc_api_key:
             print("ERROR: FireCrawl_API_KEY environment variable not set.")
             return {"error": "FireCrawl API key not configured.", "success": False}

        firecrawl_app = FirecrawlApp(api_key=fc_api_key)

        results = firecrawl_app.deep_research(
        query= query,
        max_depth=10,
        time_limit=300,
        max_urls=50,
        )
        return {
            "success": True,
            "final_analysis": results.get("data", {}).get("finalAnalysis", "No analysis found."),
            "sources_count": len(results.get("data", {}).get("sources", [])),
            "sources": results.get("data", {}).get("sources", [])
        }

    except Exception as e:
        print(f"ERROR: Deep research tool execution failed for '{query}': {e}")
        return {"error": str(e), "success": False, "final_analysis": "Deep research failed.", "sources_count": 0, "sources": []}




@function_tool
async def  get_financial_data(
    query: str,
    max_depth: int,
    time_limit: int,
    max_urls: int
) -> Dict[str, Any]:
    """
  1. Web-search via FireCrawl API for the latest, authentic sources.**Immediately retry** if the retrieved data timestamp is older than the current timestamp.
  2. Immediately calling get_current_time_in_country(user_locale) to retrieve the exact current timestamp.
  3. Querying ONLY trusted, live financial data endpoints—prioritizing Trading View.
  4. Crawling and synthesizing multiple top-tier sources.

Parameters:
  • query (str): The financial or crypto topic to investigate.
  • max_depth (int): Link levels to follow (default: 10).
  • time_limit (int): Total seconds allotted (default: 300).
  • max_urls (int): Max URLs to fetch (default: 50).
    """
    if FirecrawlApp is None:
        print("ERROR: firecrawl-python library is required for deep_research but not installed.")
        return {"error": "Deep research tool dependency missing.", "success": False}

    try:
        fc_api_key = os.getenv("FireCrawl_API_KEY")
        if not fc_api_key:
             print("ERROR: FireCrawl_API_KEY environment variable not set.")
             return {"error": "FireCrawl API key not configured.", "success": False}

        firecrawl_app = FirecrawlApp(api_key=fc_api_key)

        results = firecrawl_app.deep_research(
        query= query,
        max_depth=10,
        time_limit=300,
        max_urls=50,
        )

        return {
            "success": True,
            "final_analysis": results.get("data", {}).get("finalAnalysis", "No analysis found."),
            "sources_count": len(results.get("data", {}).get("sources", [])),
            "sources": results.get("data", {}).get("sources", [])
        }

    except Exception as e:
        print(f"ERROR: Deep research tool execution failed for '{query}': {e}")
        return {"error": str(e), "success": False, "final_analysis": "Deep research failed.", "sources_count": 0, "sources": []}
    
    

@function_tool
def get_current_time_in_country(country_tz: str = "Asia/Karachi") -> str:
    """
    Get the current date and time in a specified country's timezone.
    Provide the timezone name, e.g., "America/New_York", "Europe/London", "Asia/Tokyo". Defaults to "Asia/Karachi" if no timezone is specified.
    Use this ONLY for questions about the current time.
    """
    try:
        tz = pytz.timezone(country_tz)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S")
    except pytz.UnknownTimeZoneError:
        print(f"ERROR: Unknown timezone '{country_tz}' requested.")
        return f"Error: Unknown timezone '{country_tz}'. Please provide a valid timezone name (e.g., 'America/New_York', 'Europe/London', 'Asia/Tokyo')."
    except Exception as e:
        print(f"ERROR: Error getting time for timezone {country_tz}: {e}")
        return f"Error getting time: {str(e)}"




# --------------------------------------------------------------------------
# Step 4: Agents Definition
# --------------------------------------------------------------------------

time_teller_agent = Agent(
    instructions="""
You Always tell "current time and date".
   - **Every** response begins with calling `get_current_time_in_country("Pakistan")` (or user's locale) to fetch the precise current date and time.
   - Use its output verbatim as your header:  
     “As of [YYYY-MM-DD HH:MM:SS <TZ>] …”
""",
    name="time_teller_agent",
    handoff_description="You are an expert time teller agent. You tell current time and date.",
    tools=[get_current_time_in_country]
)


search_agent = Agent(
    instructions="""
You are a world-class "research" assistant. For **every** query retrieve live, up-to-the-minute data, incorporating the exact timestamp from the tool.
Perform a fully up-to-the-minute, research of any topic.You quickly web search for a given topic, returning latest information and summaries from a few top results.
you only answer general questions or when a brief overview is needed. you Do NOT do deep analysis or synthesis.
""",
    name="search_agent",
    handoff_description="You are an expert research agent on any topic.",
    tools=[research_topic, get_current_time_in_country]
)



deep_search_agent = Agent(
    instructions="""
You are a world-class "deep research" assistant with over a decade of expertise. Your hallmark is delivering exceptionally detailed, data-rich, and thoroughly substantiated responses that span multiple comprehensive sections and delve into every nuance of a topic.

**Core Responsibilities:**

1. **Live Data Integration**: For every query, retrieve live, up-to-the-minute data through relevant tools, including the exact UTC timestamp of retrieval.
2. **Extensive Web Research**: Conduct meticulous web research across multiple authoritative sources—prioritizing content from 2025 onward—to gather statistics, case studies, expert opinions, and emerging trends.
3. **Structured, Lengthy Analysis**: Compose responses in a multi-section format with clear headings (e.g., Overview, Data & Facts, In-Depth Analysis, Comparative Context, Expert Insights, Conclusions). Each response should be long-form (minimum 500 words) unless the user requests a specific length.
4. **Facts, Figures & Precision**: Present all numerical data—statistics, metrics, timelines, market figures—with precise values, units, and comparisons. Contextualize numbers within historical baselines or industry standards.
5. **Comprehensive Citations**: Embed citations for each key fact or statistic using the standard citation format. Provide a list of references at the end of each section.
6. **Financial Asset Insights**: When asked, deliver real-time prices, market caps, trading volumes, and basic trend analysis for any financial asset (stocks, cryptocurrencies, commodities) via get\_financial\_data, including timestamp and percentage changes.

**Tone & Style:**

* Authoritative yet approachable, guiding users step by step.
* Use clear, precise language and avoid ambiguity.
* Incorporate visual aids recommendations (e.g., tables, charts) where helpful, and reference them in-text.
* Provide summaries and key takeaways at the end of each major section.

**Response Requirements:**

* Minimum length of 500 words, with multiple paragraphs and headings.

* Rich detail, deep-dive explanations, and layered context.

* Exact timestamps and live data points clearly indicated.

* Conclude with a synthesized summary and further reading suggestions.

* **Self-Validation Check:** After drafting your response, automatically verify the word count; if under 500 words (or the user-specified minimum), continue expanding the analysis, adding examples, context, charts, and citations until the required length and depth are achieved.

* Minimum length of 500 words, with multiple paragraphs and headings.

* Rich detail, deep-dive explanations, and layered context.

* Exact timestamps and live data points clearly indicated.

* Conclude with a synthesized summary and further reading suggestions.

""",
    name="deep_search_agent",
    handoff_description="You are an expert deep researcher agent on any topic including financial topics.",
    tools=[deep_research, get_financial_data, get_current_time_in_country]
)


agent = Agent(
    instructions="""
You are a world class query analysing agent. For every query you decide which agent to handoff based on the query type.
If the query is about current time and date, you handoff to time_teller_agent.
If the query is about general research or search, you handoff to search_agent. 
If the query is about deep research on any topic including financial topics, you handoff to deep_search_agent. 
""",
    name="agent",
    handoffs=[time_teller_agent, search_agent, deep_search_agent]
    
)


# --------------------------------------------------------------------------
# The agent, tools, provider, model, and run_config are now defined
# --------------------------------------------------------------------------