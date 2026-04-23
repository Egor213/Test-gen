#!/bin/bash
# Необязательные параметры, удалятся скоро
export PYTHONDONTWRITEBYTECODE=1
export TEST=1
export AI_API_KEY=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
isort ./src
black -l 100 ./src

# Примеры запуска --project путь корня проекта, для которого будут сгенерированы тесты. --target-dir путь к директории, для которой будут сгенерированы тесты. --target-file путь к файлу, для которого будут сгенерированы тесты. --target-class путь к классу, для которого будут сгенерированы тесты. --target-function путь к функции, для которой будут сгенерированы тесты.

# python main.py --project "../url_parser/"
# python main.py --project "../Task_project/" --target-function "service/task.py::TaskService.create_task"
# python main.py --project "../Task_project/" --target-dir "service"
python main.py --project "../Task_project/" --target-function "service/task.py::TaskService.create_task"
# python main.py --project "../pet_project/" --target-dir "src/services"
# python main.py --project "../pet_project/" --target-class "src/services/pool_service/base_pool_service.py::BasePoolService"
# python main.py --project "../pet_project/" --target-function "src/services/parce_contract_service/converters.py::convert_document_to_parce_site_contract"
# python main.py --project "./project_for_testing/"


# python main.py --project "../big_func/"
# python main.py --project "../pet_project/" --target-dir "src/services/parce_contract_service"
# python main.py --project "../pet_project/" --target-file "src/services/parce_contract_service/converters.py"

# python main.py --project "../pet_project/" --target-function "src/services/parce_contract_service/parce_site_service.py::ParceSiteService.get_contract_by_id"
# python "$@"


# docker build -t my-analyzer .
# docker run --rm -v "C:/Diplom/bsc_Muravin/Task_project:/target_project" my-analyzer python main.py --project /target_project --target-function "service/task.py::TaskService.create_task"
# docker run --rm -v "C:/Diplom/bsc_Muravin/Task_project:/Task_project" -v "C:/Diplom/bsc_Muravin/Generator_Tests/logs:/app/logs"  my-analyzer python main.py --project ../Task_project --target-function "service/task.py::TaskService.create_task"
# docker exec -it 6b4e5b0b6909 sh



docker run --rm -e INPUT_PROJECT="../github/workspace/Task_project" -e INPUT_TARGET_FUNCTION="service/task.py::TaskService.create_task" -e AI_API_KEY="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" -v "$(pwd -W):/github/workspace" my-analyzer
docker run --rm -e INPUT_PROJECT="/github/workspace/test_project" -e INPUT_TARGET_FUNCTION="service/task.py::TaskService.create_task" -e AI_API_KEY="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" -v "$(pwd -W):/github/workspace" my-analyzer