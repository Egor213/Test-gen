# File path: Generator_Tests/src/app/app.py
import os

from src.app.logger import get_logger
from src.managers.config import Config
from src.managers.console import ConsoleManager
from src.orchestrator import PipelineOrchestrator


async def main():
    console_manager = ConsoleManager()
    args = console_manager.get_args()
    config = Config(config_file_path=args.config)
    config.ai_api_key = os.getenv("AI_API_KEY") or config.ai_api_key
    # i = 0
    # while True:
    #     i += 1
    orchestrator = PipelineOrchestrator(
        config,
        console_manager,
        logger=get_logger(
            "PipelineOrchestrator",
            output=config.logger.log_out,
            log_file=config.logger.log_file,
            file_level=config.logger.numeric_file_level,
            console_level=config.logger.numeric_console_level,
        ),
    )
    await orchestrator.orchestrate_pipeline()
