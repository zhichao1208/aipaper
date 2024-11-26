from crewai import Task
from crewai_tools import EXASearchTool, WebsiteSearchTool, ScrapeWebsiteTool

class AIPaperTasks:
    def __init__(self):
        # 初始化工具
        self.exa_search_tool = EXASearchTool()
        self.website_search_tool = WebsiteSearchTool()
        self.scrape_tool = ScrapeWebsiteTool()

    def find_paper_task(self):
        return Task(
            description=(
                "search for the latest papers about the given {topic},"
                "category is 'research paper',"
                "startPublishedDate is current year to date (2024)"
                "num_results=5"
            ),
            expected_output=(
                "get 5 papers from results from category of 'research paper, with link"
            ),
            tools=[self.exa_search_tool],
            agent=None  # 这里可以指定相应的 agent
        )

    def research_task(self):
        return Task(
            description=(
                "Rank the papers from find_paper_task, not just based on the publish date and total Citations,"
                "but also think about interesting and impact to podcast listener"
                "give them score"
            ),
            expected_output=(
                "choice one paper from the list"
            ),
            agent=None  # 这里可以指定相应的 agent
        )

    def validate_task(self):
        return Task(
            description=(
                "check all these new links if it's working"
                "suggest one paper with working link"
            ),
            expected_output=(
                "one paper with a replaced link from 'abs' to 'html'"
            ),
            agent=None,  # 这里可以指定相应的 agent
            tools=[self.website_search_tool]
        )

    def write_task(self):
        return Task(
            description=(
                "Write podcast title and podcast description,"
                "based on the scraped content from the scrape_full_text_task or the original link,"
                "from the selected paper HTML link."
                "make sure the catch for podcast viewer."
            ),
            expected_output=(
                "provide title, description and prompt text for NLM"
                "add paper title, link, publish date and authors at the end of description."
                "total English characters count should be less than 400."
                "add a prompt text, less than 100, short intro to podcast host, how should they talk about this paper."
            ),
            agent=None,  # 这里可以指定相应的 agent
            tools=[self.scrape_tool],
            output_json=None,  # 这里可以指定输出的 JSON 模型
            output_file="podcast_content.json"
        )
