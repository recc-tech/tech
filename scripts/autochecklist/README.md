# autochecklist

autochecklist is a framework for making interactive and partially-automated checklists.

## Demo

To see a demo, run `python -m autochecklist`.

## The Format of the Task List

The task list can be stored in a JSON file and then loaded into a `TaskGraph`. The script expects the task list to be a JSON object with the following structure. If you want to add extra fields (e.g., as comments), prefix them with an underscore.
```
{
	"name": "name_of_the_task",
	"description": "An explanation of what to do.",
	"prerequisites": ["prerequisite_task1", "prerequisite_task2"],
	"subtasks": [
		{
			"name": "subtask",
			...
		}
	],
	"only_auto": true
}
```

- The `name` field must *uniquely* identify a the task. It's a good idea to make this a valid Python function name in case you want to automate the task at some point. This basically means it should start with a letter and contain only letters, numbers, and underscores (i.e., no spaces).
- The `description` contains the instructions that will be shown to the user if the task must be completed manually.
- The `prerequisites` field is a list of the names of tasks that must be completed before the current task can be completed.
- The `subtasks` field can be used to break a task into smaller, more concrete steps. Only tasks without subtasks will be shown to the user, so there's no need to give a description for tasks with subtasks. However, you can still use tasks that have subtasks as a prerequisite. In that case, *all* the subtasks must be completed before the next task can start. Furthermore, a task with subtasks can have prerequisites. In that case, none of the subtasks will start before the prerequisite is completed.
- The `only_auto` field can be used to say that a task cannot be performed manually.

## Automating Tasks

You can automate any task by writing a Python function with the same name as the task. If the function expects inputs, the script will automatically find corresponding arguments based on the type annotation. Locating functions and arguments is handled by the `FunctionFinder` class. If the function raises an exception and does not catch it, then the script will notify the user and prompt them to complete the task manually instead.
