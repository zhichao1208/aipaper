from crewai import Agent
from crewai_tools import DirectoryReadTool, FileReadTool, WebsiteSearchTool, ScrapeWebsiteTool, EXASearchTool

class NewsroomCrew():
    def __init__(self):
        # 初始化工具
        self.directory_read_tool = DirectoryReadTool()
        self.file_read_tool = FileReadTool()
        self.website_search_tool = WebsiteSearchTool()
        self.scrape_tool = ScrapeWebsiteTool()
        self.exa_search_tool = EXASearchTool()

    def paper_finder_agent(self):
        return Agent(
            role="Senior AI Researcher",
            goal="Uncover cutting-edge AI trending and pick the top theme for podcast",
            backstory=(
                "As a part of the dynamic podcast team, "
                "You're a seasoned researcher with a knack for uncovering the latest AI developments."
                "Known for your ability to find the most relevant information and present it in a clear and concise manner."
                "Your work is crucial in paving the way "
                "for meaningful engagements and driving the company's growth."
            ),
            allow_delegation=False,
            verbose=True
        )

    def researcher_agent(self):
        return Agent(
            role="Senior AI Editor",
            goal="Uncover cutting-edge AI trending and pick the top theme for podcast",
            backstory=(
                "As a part of the dynamic podcast team, "
                "You're a seasoned researcher with a knack for uncovering the latest AI developments."
                "Known for your ability to find the most relevant information and present it in a clear and concise manner."
                "Your work is crucial in paving the way "
                "for meaningful engagements and driving the company's growth."
            ),
            allow_delegation=False,
            verbose=True
        )

    def writer_agent(self):
        return Agent(
            role="Senior content writer",
            goal="write great content for podcast",
            backstory=(
                "As a part of the dynamic podcast team, "
                "You're a seasoned content writer with a knack for uncovering the latest AI developments."
                "you can write very good content for the podcast."
                "Your work is crucial in paving the way "
                "for meaningful engagements and driving the company's growth."
            ),
            allow_delegation=False,
            verbose=True
        )