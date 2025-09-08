from typing import List, Optional, Dict, Union, Annotated, Literal
from enum import Enum
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, AfterValidator, model_validator, field_validator, ValidationError
import csv
from typing_extensions import Self
import json
from pathlib import Path
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.rate_limiters import InMemoryRateLimiter
import time

few_shot_1 = """{{
	"extracted_playbook": [		
		{{
			"step_number":1,
			"type":"ACTION",
			"title":"Identify Affected System and Version",
			"description":"Check if the system is affected by the CVE by retrieving the installed firmware version and configurations.",
			"commands":null,
			"next_step":2
		}},
		
		{{
			"step_number":2,
			"type":"CONDITION",
			"condition":"Is the system affected by the CVE?",
			"next_step":3,
			"else_step":null
		}},
		
		{{
			"step_number":3,
			"type":"PARALLEL",
			"parallel_steps":[4,5],
			"next_step":6
		}},
		
		{{
			"step_number":4,
			"type":"ACTION",
			"title":"Change standard password",
			"description":"Change the standard password in the web-based management to prevent unauthorized access, as attackers need valid credentials to exploit the system.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":5,
			"type":"ACTION",
			"title":"Review and restrict user accounts",
			"description":"Check existing user accounts for unauthorized access. Disable or remove unnecessary accounts and enforce least privilege principles.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":6,
			"type":"ACTION",
			"title":"Update firmware",
			"description":"Apply the latest security patch by updating the firmware to at least version 27.",
			"commands":null,
			"next_step":null
		}}
		
		
	],
	"start_step_number":1,
	"cve_id":"CVE-2023-6357",
	"affected_products":["Edge Controller 0752-8303/8000-0002:::< 4.5.10 (FW27)", "CC100 0751/9x01:< 04.06.03 (70)"]	
}}"""

few_shot_2 = """{{
	"extracted_playbook": [
		{{
			"step_number":1,
			"type":"ACTION",
			"title":"Identify Affected System and Version",
			"description":"Check if the system is affected by the CVE by retrieving the installed firmware version and configurations.",
			"commands":null,
			"next_step":2
		}},
		
		{{
			"step_number":2,
			"type":"CONDITION",
			"condition":"Is the system affected by the CVE?",
			"next_step":3,
			"else_step":null
		}},
		
		{{
			"step_number":3,
			"type":"SWITCH_CONDITION",
			"condition":"Which system version?",
			"cases": {{
				"Windows":4,
				"RM Shell":5
			}},
			"default":null
		}},
		
		{{
			"step_number":4,
			"type":"ACTION",
			"title":"Apply '2024-08 Cumulative Update'",
			"description":"Download and install the '2024-08 Cumulative Update' from Microsoft to patch security vulnerabilities.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":5,
			"type":"SWITCH_CONDITION",
			"condition":"Which RM Shell version?",
			"cases": {{
				"RM Shell 5 based on Windows 10 LTSB 2016":6,
				"RM Shell 5 based on Windows 10 LTSC 2019":7,
				"RM Shell 6 based on Windows 10 LTSC 2021":8
			}},
			"default":null
		}},
		
		{{
			"step_number":6,
			"type":"ACTION",
			"title":"Apply Security Patch '18-33624T' (Windows - 2024-08)",
			"description":"Install the '18-33624T Windows Cumulative Security Patch - 2024-08' to mitigate identified security risks.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":7,
			"type":"ACTION",
			"title":"Apply Security Patch '18-34182G' (Windows - 2024-08)",
			"description":"Install the '18-34182G Windows Cumulative Security Patch - 2024-08' to mitigate identified security risks.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":8,
			"type":"ACTION",
			"title":"Apply Security Patch '18-34927A' (RM Image - Windows - 2024-08)",
			"description":"Install the '18-34927A RM Image Security Patch - Windows Cumulative Security Patch 2024-08' to mitigate identified security risks.",
			"commands":null,
			"next_step":null
		}}
	
	],
	"start_step_number":1,
	"cve_id":"CVE-2024-38063",
	"affected_products":["Image <= 118-0241B: Native Windows installed on PC82****-*:Version Windows 10 IoT Enterprise LTSB 2016 < KB5041773"]
}}"""

few_shot_3 = """{{
	"extracted_playbook": [
		{{
			"step_number":1,
			"type":"ACTION",
			"title":"HTTP/2 check",
			"description":"Testing if HTTP/2 is enabled by using Openssl and Nmap Commands.",
			"commands":["echo 1 | openssl s_client -alpn h2 -connect google.com:443 -status 2>&1 | grep 'ALPN'", "nmap -p 443 --script=tls-nextprotoneg <www.google.com>"],
			"next_step":2
		}},
		
		{{
			"step_number":2,
			"type":"SWITCH_CONDITION",
			"condition":"Which system patch is suitable?",
			"cases": {{
				"Nginx":3,
				"Microsoft IIS and MsQuic":4,
				"Netscaler":5
			}},
			"default":6
		}},
	
		{{
			"step_number":3,
			"type":"ACTION",
			"title":"Ensure Secure HTTP/2 Configuration in NGINX",
			"description":"Ensure recommended default values for 'keepalive_requests' and 'http2_max_concurrent_streams' are maintained. Additionally, apply 'limit_conn' and 'limit_req' directives to mitigate excessive client requests.",
			"commands":[
				"keepalive_requests 1000;",
				"http2_max_concurrent_streams 128;",
				"limit_conn zone_name N;", 
				"limit_req zone=zone_name burst=N;"
			],
			"next_step":null
		}},
		
		{{
			"step_number":4,
			"type":"CONDITION",
			"condition":"Is the organization able to install the latest Microsoft security update?",
			"next_step":7,
			"else_step":8
		}},
		
		{{
			"step_number":7,
			"type":"ACTION",
			"title":"Install the Latest Microsoft Security Update",
			"description":"Apply the latest Microsoft security update to mitigate the identified vulnerability",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":8,
			"type":"ACTION",
			"title":"Apply Microsoft Workaround for Vulnerability Mitigation",
			"description":"Implement Microsoft's recommended workaround as an alternative mitigation measure.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":5,
			"type":"ACTION",
			"title":"Apply Netscaler Load Reduction Measures",
			"description":"Implement Netscaler's recommended configurations to reduce backend server load in load balancing and content switching environments.",
			"commands":null,
			"next_step":null
		}},
		
		{{
			"step_number":6,
			"type":"ACTION",
			"title":"Monitor Connection Statistics for Abusive Patterns",
			"description":"Track connection statistics to detect abnormal or abusive behavior. Identify clients that exceed normal usage patterns to prevent resource exhaustion attacks.",
			"commands":null,
			"next_step":9
		}},
		
		{{
			"step_number":9,
			"type":"ACTION",
			"title":"Terminate Connections Exceeding Stream Limits",
			"description":"Close connections that exceed the configured concurrent stream limit, either immediately or after detecting repeated violations.",
			"commands":null,
			"next_step":10
		}},
		
		{{
			"step_number":10,
			"type":"ACTION",
			"title":"Enforce GOAWAY Frames to Restrict New Streams",
			"description":"Implement forceful GOAWAY frames to immediately prevent further stream creation from abusive clients.",
			"commands":null,
			"next_step":11
		}},
		
		{{
			"step_number":11,
			"type":"CONDITION",
			"condition":"Have the previous mitigation steps failed to reduce the attack impact?",
			"next_step":12,
			"else_step":null
		}},
		
		
		{{
			"step_number":12,
			"type":"ACTION",
			"title":"Disable HTTP/2 and HTTP/3 to Mitigate the Threat",
			"description":"As a last resort, disable HTTP/2 and HTTP/3 to mitigate attack risks. Be aware that this may impact performance and compatibility with some clients.",
			"commands":null,
			"next_step":null
		}}
		
	],
	"start_step_number":1,
	"cve_id":"CVE-2023-44487",
	"affected_products":["Kong Gateway Enterprise: 2.8.4.4, 3.1.1.6, 3.2.2.5, 3.3.1.1, 3.4.1.1", "Kong Gateway OSS: 3.4.2", "Kong Mesh: 2.0.8, 2.1.7, 2.2.5, 2.3.3, 2.4.3", "Apache Tomcat: version 8.5.0 to version 8.5.93"]	
}}"""




df_advisories = pd.read_csv("ErrorsLLM.csv", header=0)

rate_limiter = InMemoryRateLimiter(
    requests_per_second=0.1,  # <-- Super slow! We can only make a request once every 10 seconds!!
    check_every_n_seconds=0.1,  # Wake up every 100 ms to check whether allowed to make a request,
    max_bucket_size=10,  # Controls the maximum burst size.
)


llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,
    max_tokens=None,
    rate_limiter=rate_limiter,
    #timeout=180,
    api_key="XXX",
)

list_validator_errors = []


def strip_and_validate(value: str) -> str:
    if not value or not value.strip():
        list_validator_errors.append(("field_is_empty", "Field must not be empty or only whitespace"))
    return value.strip()


validStr = Annotated[str, AfterValidator(strip_and_validate)]


class WorkflowStepType(str, Enum):
    CONDITION = 'CONDITION'
    SWITCH_CONDITION = 'SWITCH_CONDITION'
    PARALLEL = 'PARALLEL'
    ACTION = 'ACTION'


class WorkflowStepBase(BaseModel):
    """
    A concrete workflow step in a playbook process.

    Each step is uniquely identified by a step_number and is of a specific type.
    Depending on its type, the step includes only the relevant fields.
    """
    step_number: int = Field(
        description="Unique step number indicating the order."
    )
    # WorkflowStepType
    type: Literal["ACTION", "CONDITION", "SWITCH_CONDITION", "PARALLEL"] = Field(
        description="The type of this workflow step. Must be one of 'ACTION', 'CONDITION', 'SWITCH_CONDITION', or 'PARALLEL'."
    )

    @field_validator('condition', mode='after', check_fields=False)
    @classmethod
    def check_condition_is_question(cls, value: str) -> str:
        """Validate if the condition is a properly formulated question."""
        if not value.strip().endswith("?"):
            list_validator_errors.append(("condition_no_question", f"The condition '{value}' must be a valid question (ending with a '?')."))
        return value


class ActionStep(WorkflowStepBase):
    """Represents a concrete action step in a playbook process"""
    type: Literal['ACTION'] = "ACTION"  # Direkt als String setzen
    title: validStr = Field(
        description="Concise summary of the action step, describing its purpose or action in a clear and informative way."
    )
    description: validStr = Field(
        description="Detailed description of the action to be performed."
    )
    commands: Optional[List[validStr]] = Field(
        default=None,
        description="List of executable commands (e.g., shell commands) to implement the action step"
        #description="List of executable commands (e.g., shell commands) derived strictly from concrete information in the advisory text. If exact command values are not provided, the LLM should generate a syntactically correct command using placeholders (e.g., limit_conn zone_name N;). The LLM should not create speculative or assumed commands beyond what is explicitly mentioned in the advisory."
    )
    next_step: Optional[int] = Field(
        default=None,
        description="The step_number to execute after this action is completed. If no further steps follow, set 'next_step' to null."
    )


class ConditionStep(WorkflowStepBase):
    """Represents a simple true/false condition that determines which step to execute next."""
    """type: Literal[WorkflowStepType.CONDITION] = WorkflowStepType.CONDITION"""
    type: Literal['CONDITION'] = "CONDITION"
    condition: validStr = Field(
        description="A boolean condition (as a question) that must be met to proceed with the next step."
    )
    next_step: int = Field(
        description="The step_number to execute if the condition is met."
    )
    else_step: Optional[int] = Field(
        default=None,
        description="The step_number to execute if the condition is NOT met."
    )

    @model_validator(mode="after")
    def check_else_step_not_same_as_next(self) -> Self:
        if self.else_step is not None and self.else_step == self.next_step:
            list_validator_errors.append(("else_step=next_step", "else_step must not be the same as next_step."))
        return self


class SwitchConditionStep(WorkflowStepBase):
    """
    Represents a switch condition that routes execution to different steps based on the evaluated answer. Allows for more complex decision-making with multiple cases.
    """
    """type: Literal[WorkflowStepType.SWITCH_CONDITION] = WorkflowStepType.SWITCH_CONDITION"""
    type: Literal['SWITCH_CONDITION'] = "SWITCH_CONDITION"
    condition: validStr = Field(
        description="The condition (as a question) to evaluate, e.g., 'Which operating system is installed?'"
    )
    cases: Dict[validStr, int] = Field(
        description="Mapping of answer options to next workflow step_numbers. Use the key 'default' for a fallback case."
    )
    default: Optional[int] = Field(None, description="Optional default step if no cases match.")

    @model_validator(mode="after")
    def check_case_count(self) -> Self:
        # checks, if at least two different cases defined
        if len(self.cases) < 2:
            list_validator_errors.append(("not_enough_cases", f"SwitchCondition in step_number {self.step_number} must have at least two cases."))
        return self

    @model_validator(mode="after")
    def check_unique_case_targets(self) -> Self:
        unique_steps = set(self.cases.values())

        # checks, if at least two different target steps required
        if len(unique_steps) < 2:
            list_validator_errors.append(("switch_same_targets", f"SwitchCondition in step_number {self.step_number} must have at least two DIFFERENT next_step targets."))
        return self


class ParallelStep(WorkflowStepBase):
    """
    Represents a branching point in the workflow where multiple workflow steps are executed in parallel.
    Each entry in `parallel_steps` defines a separate branch that runs concurrently with the others.
    """
    """type: Literal[WorkflowStepType.PARALLEL] = WorkflowStepType.PARALLEL"""
    type: Literal['PARALLEL'] = "PARALLEL"
    parallel_steps: List[int] = Field(
        description="A list of two or more step_numbers that each start an independent branch of steps that are to be executed concurrently, even if there is only one workflow step in the branch."
    )
    next_step: Optional[int] = Field(
        default=None,
        description="The step_number to continue the workflow after all the parallel branches initiated by 'parallel_steps' have completed. If no further steps follow, set 'next_step' to null."
    )

    @model_validator(mode="after")
    def check_parallel_steps_count(self) -> Self:
        # checks, if at least two different step_numbers are present
        if len(self.parallel_steps) < 2:
            list_validator_errors.append(("parallel_not_enough_steps", f"ParallelStep with step_number {self.step_number} must contain at least two step_numbers."))
        return self

    @model_validator(mode="after")
    def check_parallel_steps_unique(self) -> Self:
        # checks, if all step_numbers are different
        if len(set(self.parallel_steps)) < len(self.parallel_steps):
            list_validator_errors.append(("parallel_no_unique_steps", f"ParallelStep with step_number {self.step_number} must contain unique step_numbers."))
        return self




# Define the Union of all step types. This will be used as the type of each step in the playbook.
WorkflowStep = Annotated[
    Union[
        ActionStep,
        ConditionStep,
        SwitchConditionStep,
        ParallelStep
    ],
    Field(discriminator="type")
]


class Playbook(BaseModel):
    """Represents an extracted cybersecurity playbook that defines a structured sequence of workflow steps for mitigating, detecting, or responding to a specific vulnerability (CVE)."""
    extracted_playbook: List[WorkflowStep] = Field(description="A list of workflow steps that define the execution flow of the playbook.")
    start_step_number: int = Field(description="The step number where the playbook execution begins.")
    cve_id: Optional[validStr] = Field(description="The CVE identifier associated with the vulnerability this playbook addresses (e.g., 'CVE-2024-38063').")
    affected_products: Optional[List[validStr]] = Field(default=None, description="A list of affected products and their version numbers that are vulnerable to the specified CVE.")

    @model_validator(mode="after")
    def check_unique_step_numbers(self) -> Self:
        step_numbers = [step.step_number for step in self.extracted_playbook]
        if len(step_numbers) != len(set(step_numbers)):
            list_validator_errors.append({"step_number_not_unique": "Each step_number must be unique!"})
        return self

    @model_validator(mode="after")
    def check_next_step_references(self) -> Self:
        step_numbers = {step.step_number for step in self.extracted_playbook}

        for step in self.extracted_playbook:
            # check next_step, if the attribute exists
            if hasattr(step, "next_step") and step.next_step is not None:
                if step.next_step not in step_numbers:
                    list_validator_errors.append(("step_reference_does_not_exist", f"next_step {step.next_step} in step_number {step.step_number} does not exist!"))

            # check else_step for ConditionStep
            if isinstance(step, ConditionStep) and step.else_step is not None:
                if step.else_step not in step_numbers:
                    list_validator_errors.append(("step_reference_does_not_exist", f"else_step {step.else_step} in step_number {step.step_number} does not exist!"))

            # check cases for SwitchConditionStep
            if isinstance(step, SwitchConditionStep):
                for case, case_step in step.cases.items():
                    if case_step not in step_numbers:
                        list_validator_errors.append(("step_reference_does_not_exist", f"Case '{case}' in step_number {step.step_number} refers to non-existent step {case_step}!"))

                # check default case (if present)
                if step.default is not None and step.default not in step_numbers:
                    list_validator_errors.append(("step_reference_does_not_exist", f"Default case in step_number {step.step_number} refers to non-existent step {step.default}!"))

            # check parallel_steps for ParallelStep
            if isinstance(step, ParallelStep):
                for parallel_step in step.parallel_steps:
                    if parallel_step not in step_numbers:
                        list_validator_errors.append(("step_reference_does_not_exist", f"Parallel step {parallel_step} in ParallelStep with step_number {step.step_number} does not exist!"))
        return self

    @model_validator(mode="after")
    def check_playbook_has_terminal_step(self) -> Self:
        terminal_step_found = any(
            isinstance(step, (ActionStep, ParallelStep)) and step.next_step is None
            for step in self.extracted_playbook
        )

        if not terminal_step_found:
            list_validator_errors.append(("no_playbook_termination_step", "Playbook must have at least one terminal step (ActionStep or ParallelStep with next_step=None) to ensure proper termination!"))
        return self


"""
with open("VDE-2025-002.json", "r", encoding="utf-8") as file:
    json_data = json.load(file)
few_shot_2 = json.dumps(json_data, indent=4)

with open("CERT-Europe-2023-074.json", "r", encoding="utf-8") as file:
    json_data = json.load(file)
few_shot_3 = json.dumps(json_data, indent=4)

with open("VDE-2025-008.json", "r", encoding="utf-8") as file:
    json_data = json.load(file)
few_shot_1 = json.dumps(json_data, indent=4)
"""

with open("VDE-2025-002.json", "r", encoding="utf-8") as file:
    json_data = json.load(file)


def write_error_csv_file(url_id, url, list_standard_errors, list_validator_errors, cert_name):
    if list_validator_errors != "":
        list_val_codes = [err[0] for err in list_validator_errors]
        list_validator_errors = list_val_codes

    with open('ErrorsLLM.csv', mode='a', newline='', encoding='utf-8') as outfileError:
        writer_error = csv.writer(outfileError)
        writer_error.writerow([url, url_id, list_standard_errors, list_validator_errors, cert_name])


def write_output_files(url, playbook_pydantic, list_standard_errors, cert_name):
    if cert_name == "EU_CERT":
        url = url.rsplit("/", 1)[0]

    url_id = url.rstrip("/").rsplit("/", 1)[-1]
    print(url_id)

    new_dir = Path(__file__).parent.parent / "Playbook Dataset" / cert_name / url_id
    new_dir.mkdir(parents=True, exist_ok=True)
    print()

    url_file = new_dir / "advisory_url.txt"
    with url_file.open("w", encoding="utf-8") as f:
        f.write(url + "\n")

    if playbook_pydantic != "":
        json_file = new_dir / f"playbook-{url_id}.json"
        with json_file.open("w", encoding="utf-8") as f:
            json.dump(playbook_pydantic.model_dump(), f, indent=4, ensure_ascii=False)

    if len(list_standard_errors) == 0 and len(list_validator_errors) == 0:
        write_error_csv_file(url_id, url, "", "", cert_name)
    elif len(list_standard_errors) > 0:
        write_error_csv_file(url_id, url, list_standard_errors, "", cert_name)
        standard_error_file = new_dir / "standard_errors.txt"
        with standard_error_file.open("w", encoding="utf-8") as f:
            for error in list_standard_errors:
                f.write(error + "\n")
    elif len(list_validator_errors) > 0:
        write_error_csv_file(url_id, url, "", list_validator_errors, cert_name)
        validator_error_file = new_dir / "validator_errors.txt"
        with validator_error_file.open("w", encoding="utf-8") as f:
            for error in list_validator_errors:
                f.write(f"{error[0]} : {error[1]}" + "\n")
        list_validator_errors.clear()


def remove_references(text: str) -> str:
    """
    Removes everything from the text after the last occurrence of the word ‘references’, including that word. If ‘references’ does not occur, the original text is returned.
    """
    last_occurrence = text.rfind("References")

    if last_occurrence == -1:
        return text

    return text[:last_occurrence].strip()


system_prompt = f"""You will receive unstructured cybersecurity advisory text describing measures to mitigate or fix software or hardware vulnerabilities. These texts may include affected systems, workarounds, recommendations, detections, and other relevant security information.

Your task is to extract a structured workflow (cybersecurity playbook) that a system administrator or security analyst can follow to mitigate the vulnerability. The extracted workflow must adhere strictly to the provided Playbook schema, including its structure, step types, and attributes and be based only on concrete information present in the input text.

**Workflow Structure:**
A workflow consists of steps that follow a sequential order, run in parallel, or branch based on conditions.
The workflow must be structured using the following step types:
- ActionStep: For executable actions. 
- ConditionStep: For yes/no decisions. 
- SwitchConditionStep: For multi-option branches.
- ParallelStep: For tasks that can run simultaneously.

**Key Rules for general Extraction:**
- Only extract information explicitly stated in the advisory text. Do not infer missing details or generate speculative steps.
- If there is no subsequent step in the workflow, set the next_step attribute to null to indicate the end of that workflow (branch).
- Use parallel steps only when the actions are both independent and thematically related, or when executing them simultaneously improves efficiency. Avoid excessive parallelization if a clear sequence is more practical.
- When using parallel steps, ensure that no more than 5 parallel branches are created. If the advisory mentions more than 5 distinct actions that could run in parallel, present them as sequential steps, group similar actions into one ActionStep, or prioritize the most critical ones to maintain clarity.
- If the recommended mitigations or recommendations are not universally applicable but are specified in the text as relevant only for certain types of organizations, include a condition step in the workflow to check if the criteria, in the advisory text written in CAPSLOCK, apply. (e.g., "RECOMMENDATIONS FOR INSTITUTIONS WITH RETAIL PAYMENT SYSTEMS, SOFTWARE MANUFACTURER or NETWORK DEFENDER" -> ConditionStep: "Retail Payment Systems in use?")  
- If no "cve_id" is found during extraction, check if the advisory has a general title summarizing the advisory and use it as "cve_id".
- If there are multiple ways to achieve the same mitigation or configuration change, they should be grouped as conditional options rather than sequential steps. Use a ConditionStep or SwitchConditonStep to check which method is applicable in the given context. For example, disabling a feature X can be done either via the user interface or by modifying a configuration file -> SwitchConditionStep: cases "user interface" and "configuration file"
- WORDS IN ALL CAPS (e.g., EVALUATE TENANT SETTINGS, CREATE A FORENSICALLY READY ORGANIZATION) may indicate that the following steps belong to a common thematic group. Use a ConditionStep to determine whether this group should be applied. For example: "Tenant Setting evaluation needed?" → Yes: Execute relevant steps, No: Skip this section.
- Ensure that every step is properly linked through next_step, cases, parallel_steps, or else_step, forming a seamless process flow. Every step must be reachable from the start, ensuring a complete and logical execution path.  
- If the advisory text is very long, focus on the sections containing mitigations and recommendations, as earlier parts may only describe attacker tactics and techniques that are not relevant for extracting the playbook workflow.

**Key Rules for Command Extraction:**
Each ActionStep includes a "commands" attribute, which is a list of executable commands to implement that action. Follow these rules for command extraction:
1. Direct Command Extraction:
If the advisory text contains a fully executable command (e.g., echo 1 | openssl s_client -alpn h2 -connect google.com:443 -status 2>&1 | grep 'ALPN'), extract the command exactly as it appears and include it in the commands list.

2. Command Generation from Partial Information:
If the advisory text does not provide a fully executable command but includes:
	- The system context (for example, nginx), and
	- A partial command fragment (for example, "'keepalive_requests' should be kept at the default setting of 1000 requests"),
Then generate a concrete, executable command based on the provided fragment and context (e.g., keepalive_requests 1000;).

If certain parameters are missing during generation, you may use placeholders (e.g., keepalive_requests N;).

3. No Command Information:
If the advisory text does not include a full command or even a command fragment (for instance, it only describes an action like "Track connection statistics and identify abusive connections"), then do not generate any command.
In such cases, set the commands attribute to null.

**Example Outputs:**
Below are three structured playbook examples that align with the schema you must follow. These illustrate different workflow structures, including sequential execution, parallel execution, and conditional branching.

###example_1_start###
    {few_shot_1}
###example_1_end###

###example_2_start###
    {few_shot_2}
###example_2_end###

###example_3_start###
    {few_shot_3}
###example_3_end###

Ensure that all extracted workflows maintain consistency with this format."""


prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("human", "{text}"),
    ]
)


llm_structured = llm.with_structured_output(Playbook, method="function_calling")

#prompt = prompt_template.invoke({"text": text})
#ai_msg = llm_structured.invoke(prompt)

#cert_name = "CISA_ICS"
#cert_name = "EU_CERT"
#cert_name = "VDE_CERT"
#cert_name = "CISA" # - If the advisory text is very long, focus on the sections containing mitigations and recommendations, as earlier parts may only describe attacker tactics and techniques that are not relevant for extracting the playbook workflow.
cert_name = "CISA_NEW"
#x = 0
# open and read CSV file
# security_advisories_eu_cert.csv
# security_advisories_cisa.csv
# cisa_SA_22.csv
# cisa_SA_23.csv
# cisa_SA_24.csv
# security_advisories_vde.csv
# cisa_ICS_24.csv
# cisa_ICS_25.csv
# cisa_SA_18.csv
# cisa_SA_19.csv
# cisa_SA_20.csv
# cisa_SA_21.csv
with open('cisa_SA_21.csv', newline='', encoding='utf-8') as csvfile:
    readerAdvisory = csv.DictReader(csvfile)

    counter = 0
    for row in readerAdvisory:
        counter += 1
        url = row['URL']

        if cert_name == "EU_CERT":
            url_check = url.rsplit("/", 1)[0]
        else:
            url_check = url

        if url_check in df_advisories["URL"].values:
            continue

        advisory_text = row['Content']
        #print(advisory_text)
        if cert_name == "EU_CERT":
            advisory_text = remove_references(advisory_text)

        try:
            #print(system_prompt)
            #print(prompt_template.input_variables)
            prompt = prompt_template.invoke({"text": advisory_text})
            print("\n")
            print(f"start request: {url}")
            tic = time.time()
            ai_msg = llm_structured.invoke(prompt)
            toc = time.time()
            print(f"end request: {url}")
            print(f"request time: {toc - tic}")
            # ai_msg = llm_structured.invoke(prompt, config={"method": "function_calling"})
            # ai_msg = llm.invoke(prompt)
            #ai_msg = Playbook(**json_data)
            #print(ai_msg)

            #ai_msg.content
            write_output_files(url, ai_msg, [], cert_name)

        except ValidationError as e:
            print(e)
            list_standard_errors = [error["type"] for error in e.errors()]
            write_output_files(url, "", list_standard_errors, cert_name)
        except ValueError as error:
            print(error)
            write_output_files(url, "", [str(error)], cert_name)
        except Exception as exception:
            print(exception)
            write_output_files(url, "", [str(exception)], cert_name)

    print(f"count Advisories: {counter}")
