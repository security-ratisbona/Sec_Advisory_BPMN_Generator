import json
import math
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.dom import minidom
import calculate_coordinates
from pathlib import Path
import shutil


bpmn_elements_list = {}
# element
#def extract_logic(playbook_steps_list):
sequence_flow_list = {}
action_list = {}


# Counter for the parallel levels
parallel_levels = {}
level_counter = 1
join_list = []


def calculate_join_next(id):
    join_next = ""
    if join_list:
        for index, j in enumerate(join_list):
            if j == id:
                if index > 0:
                    join_next = join_list[index - 1]
                    return join_next
                else:
                    return "EndEvent"
    else:
        return "EndEvent"


def add_elements(playbook_steps_list):
    task_counter = 1
    ex_counter = 1
    par_counter = 1
    sw_counter = 1

    join_tracker = {}

    # tracker excl gateway
    steps_reunited = False
    ET.SubElement(process, f"{{{bpmn_ns}}}startEvent", {
        "id": "StartEvent",
        "name": "Start"
    })

    ET.SubElement(process, f"{{{bpmn_ns}}}endEvent", {
        "id": "EndEvent",
        "name": "End"
    })
    bpmn_elements_list["StartEvent"] = {"step": 0, "next": "", "type":"StartEvent"}
    max_step = 0
    for i, p in enumerate(playbook_steps_list, start=1):
        max_step += 1
        type = p['type']
        if type == "CONDITION" or type == "SWITCH_CONDITION" or type == "PARALLEL":
            max_step +=1

    previous_step = 0
    current_last_step = max_step
    # Extracting the Elements into the workflow list && creating the bpmn elements
    for i, p in enumerate(playbook_steps_list, start=1):
        type = p['type']
        id =  f"Task_{task_counter}"

        while True:
            sorted_joins = dict(sorted(join_tracker.items(), key=lambda item: item[1]))
            first_key = next(iter(sorted_joins), None)
            if first_key is not None:
                if sorted_joins[first_key] <= previous_step + 1:
                    join_tracker.pop(first_key)
                else:
                    last_join = sorted_joins[first_key]
                    break
            else:
                last_join = None
                break

        if type == 'ACTION':
            task_name = p['title']
            next_step = p['next_step']
            step_number = p["step_number"]
            if next_step is None:
                if last_join is not None:
                    next_step = last_join
                else:
                    next_step = current_last_step
            if p["commands"] is not None:
                commands = p["commands"]
                script_task = ET.SubElement(process, f"{{{bpmn_ns}}}scriptTask", {
                    "id": id,
                    "name": task_name
                })
                script = ET.SubElement(script_task, f"{{{bpmn_ns}}}script")
                # WRITE HERE
                text = f"console.log(\"{commands}\");"
                script.text = text
            elif "classification" in p:
                classification = p["classification"]
                actions = None
               # print(classification)
                if classification == "Service Task":
                    service_task = ET.SubElement(process, f"{{{bpmn_ns}}}serviceTask", {
                        "id": id,
                        "name": task_name
                    })

                    if "OpenC2" in p:
                        actions = p["OpenC2"]
                        action_list[id] = {"actions": actions}
                        # Create the annotation
                        annotation_id = f"{id}_annotation"
                        action_list[id]["annotation_id"] = annotation_id
                        text_annotation = ET.SubElement(process, f"{{{bpmn_ns}}}textAnnotation", {
                            "id": annotation_id
                        })
                        text = ET.SubElement(text_annotation, f"{{{bpmn_ns}}}text")
                        text.text = actions

                        # Link task <-> annotation
                        association_id = f"{id}_association"
                        ET.SubElement(process, f"{{{bpmn_ns}}}association", {
                            "id": association_id,
                            "sourceRef": id,
                            "targetRef": annotation_id
                        })
                        action_list[id]["association_id"] = association_id
                    else:
                        actions = None

                elif classification == "Human Task":
                    human_task = ET.SubElement(process, f"{{{bpmn_ns}}}userTask", {
                        "id": id,
                        "name": task_name
                    })
                    actions = None

            else:
                ET.SubElement(process, f"{{{bpmn_ns}}}task", {
                    "id": id,
                    "name": task_name
                })
                actions = None

            if next_step == step_number:
                next_step += 1

            # Assign Value
            bpmn_elements_list[f"Task_{task_counter}"] = {"step": step_number, "next": next_step, "type": type}
            try:
                if actions is not None:
                    bpmn_elements_list[f"Task_{task_counter}"]["actions"] = actions
            except NameError:
                print("Actions not defined")

            if i == 1:
                bpmn_elements_list["StartEvent"]["next"] = f"Task_{task_counter}"
            task_counter += 1

            previous_step = step_number

        elif type == 'CONDITION':
            join_list.append(f"GW_join_excl_{ex_counter}")
            step_number = p["step_number"]
            step_join = 0
            text = p['condition']
            next_step_value = p['next_step']
            else_step = p['else_step']
         #   print(else_step)
            if else_step is None:
                else_step = calculate_join_next(f"GW_join_excl_{ex_counter}")
                step_join = current_last_step - 0.5
                current_last_step -= 0.5
            else:
                step_join = else_step - 0.5
            join = f"GW_join_excl_{ex_counter}"

            ET.SubElement(process, f"{{{bpmn_ns}}}exclusiveGateway", {
                "id": f"GW_split_excl_{ex_counter}",
                "name": text
            })
            ET.SubElement(process, f"{{{bpmn_ns}}}exclusiveGateway", {
                "id": f"GW_join_excl_{ex_counter}"
            })

            join_tracker[f"GW_join_excl_{ex_counter}"] = step_join

            # Assign Value
            bpmn_elements_list[f"GW_split_excl_{ex_counter}"] = {"step": step_number, "next": [next_step_value, f"GW_join_excl_{ex_counter}"], "join":join, "type": f"{type}_SPLIT"}
            bpmn_elements_list[f"GW_join_excl_{ex_counter}"] = {"step": step_join, "next": else_step , "prev":[f"GW_split_excl_{ex_counter}"],"split": f"GW_split_excl_{ex_counter}", "type": f"{type}_JOIN"}
            if i == 1:
                bpmn_elements_list["StartEvent"]["next"] = f"GW_split_excl_{ex_counter}"
            ex_counter += 1
            previous_step = step_number

        elif type == 'PARALLEL':
            join_list.append(f"GW_join_para_{par_counter}")
            step = p["step_number"]
            parallel_steps  = p["parallel_steps"]
            next_step = p["next_step"]
            step_join = 0
            ET.SubElement(process, f"{{{bpmn_ns}}}parallelGateway", {
                "id": f"GW_split_para_{par_counter}"
            })
            ET.SubElement(process, f"{{{bpmn_ns}}}parallelGateway", {
                "id": f"GW_join_para_{par_counter}"
            })
            join_list.append(f"GW_join_para_{par_counter}")

            if next_step is None:
                next_step = calculate_join_next(f"GW_join_para_{par_counter}")
                step_join = current_last_step - 1
                current_last_step -= 1
            else:
                step_join = next_step - 0.5
            # Assign Value
            join_tracker[f"GW_join_para_{par_counter}"] = step_join
            bpmn_elements_list[f"GW_split_para_{par_counter}"] = {"step": step, "parallel_steps": parallel_steps, "join":f"GW_join_para_{par_counter}", "type": "PARALLEL_SPLIT"}
            bpmn_elements_list[f"GW_join_para_{par_counter}"] = {"step": step_join, "previous": [], "next":next_step,"split":f"GW_split_para_{par_counter}", "type": "PARALLEL_JOIN"}
            if i == 1:
                bpmn_elements_list["StartEvent"]["next"] = f"GW_split_para_{par_counter}"
            par_counter += 1
            previous_step = step

        elif type == 'SWITCH_CONDITION':
            join_list.append(f"GW_join_switch_{sw_counter}")
            step = p["step_number"]
            cases = list(p['cases'].values())
            default = p["default"]
            text = p["condition"]

            longest_path_check = []
            step_join = 0
            final_merge_step = 0

            for c in cases:
                for j, pl in enumerate(playbook_steps_list, start=1):
                    if pl["step_number"] == c:
                        current_next_step = pl["next_step"]
                        if current_next_step is not None and current_next_step >= final_merge_step:
                            final_merge_step = current_next_step
                        if current_next_step is not None and step_join < current_next_step:
                            step_join = current_next_step - 0.5
                        if current_next_step is None:
                            final_merge_step = current_last_step

            if default is None and step_join == 0:
                default = calculate_join_next(f"GW_join_switch_{sw_counter}")
                step_join = current_last_step - 1
                current_last_step -= 1
            elif step_join == 0:
                step_join = default - 0.5

            ET.SubElement(process, f"{{{bpmn_ns}}}exclusiveGateway", {
                "id": f"GW_split_switch_{sw_counter}",
                "name": text
            })
            ET.SubElement(process, f"{{{bpmn_ns}}}exclusiveGateway", {
                "id": f"GW_join_switch_{sw_counter}"
            })

            join_tracker[f"GW_join_switch_{sw_counter}"] = step_join
            ## Assign Values
            bpmn_elements_list[f"GW_split_switch_{sw_counter}"] = {"step": step, "cases": cases,
                                                                  "join": f"GW_join_switch_{sw_counter}",
                                                                  "type": "SWITCH_SPLIT"}
            bpmn_elements_list[f"GW_join_switch_{sw_counter}"] = {"step": step_join, "previous": [], "next": final_merge_step, "split":f"GW_split_switch_{sw_counter}",
                                                                 "type": "SWITCH_JOIN"}
            if i == 1:
                bpmn_elements_list["StartEvent"]["next"] = f"GW_split_switch_{sw_counter}"
            sw_counter +=1
            previous_step = step_number

    key_last = ""
    max_step_corrector = 0
    for i in bpmn_elements_list:
        if bpmn_elements_list[i]["step"] > max_step_corrector:
            max_step_corrector = bpmn_elements_list[i]["step"]
    if (max_step - max_step_corrector) > 1:
        max_step = max_step_corrector + 1
    else:
        max_step += 1
    bpmn_elements_list["EndEvent"] = {"step": max_step, "type": "EndEvent"}
    # Sort dictionary items by the 'step' value
    sorted_items = sorted(bpmn_elements_list.items(), key=lambda x: x[1].get('step', float('inf')))

    # Convert back to dict if needed
    bpmn_elements_list.clear()
    bpmn_elements_list.update(dict(sorted_items))

    rough_string = ET.tostring(definitions, encoding="utf-8")
  #  print(rough_string)
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # Write the pretty XML to file
    with open("output.bpmn", "w", encoding="utf-8") as f:
        f.write(pretty_xml)


def find_step(step):
    else_return = None
    for i in bpmn_elements_list:
        if "step" in bpmn_elements_list[i]:
            if step == bpmn_elements_list[i]["step"]:
                return i


def add_sequence_flow():
    sequence_flow_id = 0
    for i, el in enumerate(bpmn_elements_list):
        # Start Event SequenceFlow
        id_start = el

        if bpmn_elements_list[el]["type"] == "StartEvent":
            id_target = bpmn_elements_list[el]["next"]

            ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                "id": f"SequenceFlow_{sequence_flow_id}",
                "sourceRef": id_start,
                "targetRef": id_target
            })

            sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
            sequence_flow_id += 1

        # Task Sequence Flow
        if bpmn_elements_list[el]["type"] == "ACTION":
            if isinstance(bpmn_elements_list[el]["next"], (int)):
                id_target = find_step(bpmn_elements_list[el]["next"])
            elif isinstance(bpmn_elements_list[el]["next"], (float)):
                id_target = find_step(bpmn_elements_list[el]["next"])
            else:
                id_target = bpmn_elements_list[el]["next"]

            ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                "id": f"SequenceFlow_{sequence_flow_id}",
                "sourceRef": id_start,
                "targetRef": id_target
            })

            sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
            sequence_flow_id += 1

        # Task Sequence Flow
        if bpmn_elements_list[el]["type"] == "PARALLEL_SPLIT":
            for p in bpmn_elements_list[el]["parallel_steps"]:
                id_target = find_step(p)

                ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                    "id": f"SequenceFlow_{sequence_flow_id}",
                    "sourceRef": id_start,
                    "targetRef": id_target
                })
                sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
                sequence_flow_id += 1

        if bpmn_elements_list[el]["type"] == "PARALLEL_JOIN":

            if isinstance(bpmn_elements_list[el]['next'],(int)):
                id_target = find_step(bpmn_elements_list[el]['next'])
            else:
                id_target = bpmn_elements_list[el]['next']

            ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                "id": f"SequenceFlow_{sequence_flow_id}",
                "sourceRef": id_start,
                "targetRef": id_target
            })

            sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
            sequence_flow_id += 1

        if bpmn_elements_list[el]["type"] == "CONDITION_SPLIT":
            for n in bpmn_elements_list[el]['next']:
                if isinstance(n, (int)):
                    id_target = find_step(n)
                    ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                        "id": f"SequenceFlow_{sequence_flow_id}",
                        "sourceRef": id_start,
                        "targetRef": id_target
                    })
                    sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
                    sequence_flow_id += 1
                else:
                    # here if conditional statement, dann neues End gateway
                    id_target = n

                    ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                        "id": f"SequenceFlow_{sequence_flow_id}",
                        "sourceRef": id_start,
                        "targetRef": id_target
                    })

                    sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
                    sequence_flow_id += 1

        if bpmn_elements_list[el]["type"] == "CONDITION_JOIN":
            c_next = bpmn_elements_list[el]['next']
            if isinstance(bpmn_elements_list[el]['next'],(int)):
                id_target = find_step(bpmn_elements_list[el]['next'])
            elif isinstance(bpmn_elements_list[el]['next'],(float)):
                id_target = find_id_for_step(bpmn_elements_list[el]['next'])
            else:
                id_target = bpmn_elements_list[el]['next']

            ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                "id": f"SequenceFlow_{sequence_flow_id}",
                "sourceRef": id_start,
                "targetRef": id_target
            })

            sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
            sequence_flow_id += 1

        if bpmn_elements_list[el]["type"] == "SWITCH_SPLIT":
            # id_start
            for c in bpmn_elements_list[el]["cases"]:
                if isinstance(c,(int)):
                    id_target = find_step(c)
                else:
                    id_target = c
                ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                    "id": f"SequenceFlow_{sequence_flow_id}",
                    "sourceRef": id_start,
                    "targetRef": id_target
                })
                sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
                sequence_flow_id += 1

        if bpmn_elements_list[el]["type"] == "SWITCH_JOIN":
            if isinstance(bpmn_elements_list[el]["next"], int):
                id_target = find_step(bpmn_elements_list[el]["next"])
            elif isinstance(bpmn_elements_list[el]['next'],(float)):
                id_target = find_id_for_step(bpmn_elements_list[el]['next'])
            else:
                id_target = bpmn_elements_list[el]["next"]
            ET.SubElement(process, f"{{{bpmn_ns}}}sequenceFlow", {
                "id": f"SequenceFlow_{sequence_flow_id}",
                "sourceRef": id_start,
                "targetRef": id_target
            })
            sequence_flow_list[f"SequenceFlow_{sequence_flow_id}"] = {"source": id_start, "target": id_target}
            sequence_flow_id += 1

    rough_string = ET.tostring(definitions, encoding="utf-8")

    # Use minidom to pretty-print it
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    # Write the pretty XML to file
    with open("output.bpmn", "w", encoding="utf-8") as f:
        f.write(pretty_xml)


def calculate_horizontal_amount():
    dim_counter = 0
    current_parallel = False
    current_switch = False
    next_switch = []
    switch_left = []
    parallel_left = []
    next_parallel = []
    current_join = ""
    current_switch_join = ""
    for i in bpmn_elements_list:
        if bpmn_elements_list[i]["type"] in ["StartEvent","EndEvent","CONDITION_SPLIT","PARALLEL_SPLIT","PARALLEL_JOIN","CONDITION_JOIN", "SWITCH_SPLIT","SWITCH_JOIN"]:
            dim_counter += 1
            if bpmn_elements_list[i]["type"] == "PARALLEL_SPLIT":
                current_parallel = True
                current_join = bpmn_elements_list[i]["join"]
                parallel_left = list(bpmn_elements_list[i]["parallel_steps"])
            if bpmn_elements_list[i]["type"] == "SWITCH_SPLIT":
                current_switch = True
                switch_left = list(bpmn_elements_list[i]["cases"])
        if bpmn_elements_list[i]["type"] == "ACTION":
            if bpmn_elements_list[i] in switch_left and current_switch:
                switch_left.remove(bpmn_elements_list[i])
                if bpmn_elements_list[i]["next"] != current_switch_join:
                    next_switch.append(bpmn_elements_list[i]["next"])
            if current_switch and not switch_left:
                dim_counter += 1
                if not next_switch:
                    current_switch = False
            if not current_switch and switch_left:
                current_switch = next_switch
                next_switch = []
            if bpmn_elements_list[i] in parallel_left and current_parallel:
                parallel_left.remove(bpmn_elements_list[i])
                if bpmn_elements_list[i]["next"] != current_join:
                    next_parallel.append(bpmn_elements_list[i]["next"])
            if current_parallel and not parallel_left:
                dim_counter += 1
                if not next_parallel:
                    current_parallel = False
            if not current_parallel and parallel_left:
                current_parallel = next_parallel
                next_parallel = []
    return dim_counter


def find_id_for_step(i):
    step_number = i
    if isinstance(step_number, int):
        found_keys = []
        for key, value in bpmn_elements_list.items():
            if isinstance(value, dict) and value.get("step") == step_number:
                found_keys.append(key)
            if value.get('step') == step_number:
                return key
    elif isinstance(step_number, float):
        for key, value in bpmn_elements_list.items():
            if value.get('step') == step_number:
                return key
    else:
        return step_number
    #    if len(found_keys) == 1:
     #       return found_keys[0]
      #  else:
      #      for key in found_keys:
       #         if bpmn_elements_list[key]["type"] == "ACTION":
        #            return key

def add_parallel_level(lv):
    counter = lv
    for el in bpmn_elements_list:
        type = bpmn_elements_list[el]['type']
        if type == "PARALLEL_SPLIT":
            steps = bpmn_elements_list[el]["parallel_steps"]
            join_id = bpmn_elements_list[el]['join']
            still_going = True
            next_level = []
            parallel_levels[counter] = el
            counter += 1
            while still_going:
                parallel_levels[counter] = steps
                counter += 1
                for n in steps:
                    id = find_id_for_step(n)
                    if id == join_id:
                        next_level.append(join_id)
                    elif bpmn_elements_list[id]["type"] == "ACTION":
                        next_level.append(bpmn_elements_list[id]["next"])
                next_level = [item for item in next_level if item != join_id]

                if not next_level:
                    still_going = False
                    parallel_levels[counter] = join_id
                    counter += 1
                else:
                    steps = next_level
    new_counter = counter
    for para in parallel_levels:
        if isinstance(parallel_levels[para], list):
            new_list = []
            for i in parallel_levels[para]:
                id = find_id_for_step(i)
                new_list.append(id)
            parallel_levels[para] = new_list
    return new_counter


def find_conditional_parts(condi):
    nexts = list(bpmn_elements_list[condi]["next"])
    join = bpmn_elements_list[condi]["join"]
    return_dict = {}
    return_dict["join"] = join
    condi_tasks = []
    while len(nexts) > 0:
        i = nexts.pop(0)
        if isinstance(i, int):
            id = find_step(i)
            if bpmn_elements_list[id]["type"] == "ACTION":
                next_step = bpmn_elements_list[id]["next"]
                if next_step is None or isinstance(next_step, float):
                    condi_tasks.append(id)
                else:
                    nexts.append(next_step)
    return_dict["steps"] = condi_tasks
    return return_dict

def fix_step_order():
    sorted_steps = sorted(bpmn_elements_list.items(), key=lambda x: x[1]["step"])
    highest_non_step = 0
    highest_step = 0
    end_step = 0
    counter = 0
    for key, data in reversed(sorted_steps):  # skip the very last (EndEvent)
        if data.get("type") == "EndEvent":
            end_step = data["step"]
            counter += 1
        elif counter == 1:
            highest_step = data["step"]
            counter += 1
        elif counter == 2:
            break

    for key, data in reversed(sorted_steps[:-1]):  # skip the very last (EndEvent)
        if data.get("type") != "ACTION":
            highest_non_step = data["step"]
            break

    for i in bpmn_elements_list:
        id = i
        step = bpmn_elements_list[i]["step"]
        type = bpmn_elements_list[i]["type"]
        if "Task" in id:
            next_step = bpmn_elements_list[i]["next"]
            if isinstance(next_step, float):
                if step <= highest_non_step:
                    bpmn_elements_list[i]["next"] = highest_non_step
                else:
                    if next_step > highest_step:
                        bpmn_elements_list[i]["next"] = end_step
            elif isinstance(next_step, int):
                if next_step > highest_step:
                    bpmn_elements_list[i]["next"] = end_step
def enrich_bpmn_elements():
    global level_counter
    last_join = []
    current_switch = {}
    current_parallel = {}
    current_condition = {}
    last_join_switch = 0

    condi_tracker = {}

    fix_step_order()

    for i in bpmn_elements_list:
        id = i
        step = bpmn_elements_list[i]["step"]
        type = bpmn_elements_list[i]["type"]

        if "GW_split_para" in id:
            parallel_steps = list(bpmn_elements_list[i]["parallel_steps"])
            join = bpmn_elements_list[i]["join"]
            current_parallel[id] = {"parallel_steps": parallel_steps, "join": join}
        if "GW_split_switch" in id:
            cases = list(bpmn_elements_list[i]["cases"])
            join = bpmn_elements_list[i]["join"]
            last_join_switch = float(bpmn_elements_list[join]["step"])
            current_switch["id"] = {"cases": cases, "join":join}
        if "GW_split_excl" in id:
            next_step = bpmn_elements_list[i]["next"]
            join = bpmn_elements_list[i]["join"]
            join_next =  bpmn_elements_list[join]["next"]
            condi_tracker[id] = find_conditional_parts(i)
            if join_next != "EndEvent":
                current_condition[id] = {"join": join, "current": next_step[0]}
        if "Task" in id:
            next_step = bpmn_elements_list[i]["next"]
            if isinstance(next_step, float) or next_step is None:
                for condi in condi_tracker:
                    condi_steps = list(condi_tracker[condi]["steps"])
                    task_join = condi_tracker[condi]["join"]
                    if id in condi_steps:
                        bpmn_elements_list[id]["next"] = task_join
                        # Also update next_step locally if needed
                        next_step = task_join
            for x in current_switch:
                if current_switch[x]["cases"]:
                    if step in current_switch[x]["cases"]:
                        if next_step is None:
                            next_step = current_switch[x]["join"]
                        else:
                            if next_step >= last_join_switch and last_join_switch != 0:
                                next_step = bpmn_elements_list[current_switch[x]["join"]]["step"]
                            else:
                                current_switch[x]["cases"].remove(step)
                                current_switch[x]["cases"].append(next_step)
            for x in current_parallel:
                if current_parallel[x]["parallel_steps"]:
                    if step in current_parallel[x]["parallel_steps"]:
                        if next_step is None:
                            next_step = current_parallel[x]["join"]
                        else:
                            current_parallel[x]["parallel_steps"].remove(step)
                            current_parallel[x]["parallel_steps"].append(next_step)
            for x in current_condition:
                if step == current_condition[x]["current"]:
                    if next_step is None:
                        next_step = current_condition[x]["join"]
                    else:
                        current_condition[x]["current"] = next_step

            if next_step is None:
                next_step = "EndEvent"

            bpmn_elements_list[id]["next"] = next_step

        if "GW_join_" in id:
            step = bpmn_elements_list[id]["step"]
            current_next = bpmn_elements_list[id]["next"]
            next_id = find_id_for_step(current_next)
            cur_next_step = bpmn_elements_list[next_id]["step"]
            right_next = ""
            right_step = True
            if cur_next_step <= step:
                right_step = False
            if not right_step:
                for c in bpmn_elements_list:
                    if bpmn_elements_list[c]["step"] > step:
                        right_next = bpmn_elements_list[c]["step"]
                        break
                bpmn_elements_list[id]["next"] = right_next


def insert_before(index, old_list, insert_el):
    new_dict = OrderedDict()
    for id, item in old_list.items():
        if id == index:
            new_dict[index]


def draw_elements():
    ##<bpmndi:BPMNShape id="TextAnnotation_19yl77m_di" bpmnElement="Task_1_Annotation">
            #  <dc:Bounds x="400" y="80" width="99.98924268502583" height="29.999462134251292" />
            #  <bpmndi:BPMNLabel />
            #   </bpmndi:BPMNShape>

    for c in coordinates_list:
       # print(coordinates_list[c])
        shape = ET.SubElement(plane, f"{{{bpmndi_ns}}}BPMNShape", {
            "id": f"{c}_di",
            "bpmnElement": c
        })
        ET.SubElement(shape, f"{{{dc_ns}}}Bounds", {
            "x": f"{coordinates_list[c]['x']}",
            "y": f"{coordinates_list[c]['y']}",
            "width": f"{coordinates_list[c]['width']}",
            "height": f"{coordinates_list[c]['height']}"
        })
        if "Task_" in c:

            if "actions" in bpmn_elements_list[c]:
                actions = bpmn_elements_list[c]["actions"]
                association_id = action_list[c]["association_id"]
                annotation_id = action_list[c]["annotation_id"]

                ann_shape = ET.SubElement(plane, f"{{{bpmndi_ns}}}BPMNShape", {
                "id": f"{annotation_id}_di",
                "bpmnElement": annotation_id
                })
                y_anno = coordinates_list[c]['y']
                y_anno -= 50
                x_anno = coordinates_list[c]['x']
                x_anno -= 15
                ET.SubElement(ann_shape, f"{{{dc_ns}}}Bounds", {
                    "x": f"{x_anno}",
                    "y": f"{y_anno}",
                    "width": f"{100}",
                    "height": f"{30}"
                })
                ET.SubElement(ann_shape, f"{{{bpmndi_ns}}}BPMNLabel")

                ann_edge = ET.SubElement(plane, f"{{{bpmndi_ns}}}BPMNEdge", {
                    "id": f"{association_id}_di",
                    "bpmnElement": association_id
                })
                ET.SubElement(ann_edge, f"{{{di_ns}}}waypoint", {
                    "x": f"{coordinates_list[c]['x']}",
                    "y": f"{coordinates_list[c]['y']}"
                })
                ET.SubElement(ann_edge, f"{{{di_ns}}}waypoint", {
                    "x": f"{x_anno}",
                    "y": f"{y_anno + 30}"
                })


condition_level = 0


def write_BPMNEdges():
    global condition_level
    dimensions, CENTRAL_AXIS = calculate_coordinates.calculate_dimensions(bpmn_elements_list, sequence_flow_list)
    split_line = CENTRAL_AXIS*1.5
    # waypoint-x is element-x plus widht; waypoint-y is element-y plus 1/2 * height
    amount_gw_follows = {}
    for s in sequence_flow_list:
        starting_point = sequence_flow_list[s]["source"]
        connecting_point = sequence_flow_list[s]["target"]
        if "GW_split_switch" in starting_point or "GW_split_para" in starting_point:
            if starting_point in amount_gw_follows:
                amount_gw_follows[starting_point] += 1
            else:
                amount_gw_follows[starting_point] = 1
        if "GW_join_switch" in connecting_point or "GW_join_para" in connecting_point:
            if connecting_point in amount_gw_follows:
                amount_gw_follows[connecting_point] += 1
            else:
                amount_gw_follows[connecting_point] = 1

    print(f"Split follows \n {amount_gw_follows}")
    sources_seen = []
    splits_seen = {}
    for s in sequence_flow_list:
        edge = ET.SubElement(plane, f"{{{bpmndi_ns}}}BPMNEdge", {
            "id": f"{s}_di",
            "bpmnElement": s
        })
        starting_point = sequence_flow_list[s]["source"]
        starting_type = bpmn_elements_list[starting_point]["type"]

        if "GW_split_switch" in starting_point or "GW_split_para" in starting_point:
            if starting_point in splits_seen:
                splits_seen[starting_point] += 1
            else:
                splits_seen[starting_point] = 1

        connecting_point = sequence_flow_list[s]["target"]
        connection_type = bpmn_elements_list[connecting_point]["type"]

        if "GW_join_switch" in connecting_point or "GW_join_para" in connecting_point:
            if connecting_point in splits_seen:
                splits_seen[connecting_point] += 1
            else:
                splits_seen[connecting_point] = 1

        starting_x =  coordinates_list[starting_point]['x']
        connection_x = coordinates_list[connecting_point]['x']

        starting_x_offset = calculate_coordinates.calculate_x_offset(starting_x, starting_type)


        starting_y = coordinates_list[starting_point]['y']
        connection_y = coordinates_list[connecting_point]['y']

        start_y_offset = calculate_coordinates.calculate_offset(starting_y, starting_type)
        con_y_offset = calculate_coordinates.calculate_offset(connection_y, connection_type)

        if "GW_split_switch" in starting_point or "GW_split_para" in starting_point:
            if splits_seen[starting_point] != amount_gw_follows[starting_point]:
                starting_x_offset -= 18
                start_y_offset -= 18

      #  if "GW_join_switch" in connecting_point or "GW_join_para" in connecting_point:
       #     if splits_seen[connecting_point] != amount_gw_follows[connecting_point]:
        #        connection_x += 18
         #       con_y_offset -= 18

        if starting_type == "CONDITION_SPLIT" and connection_type == "CONDITION_JOIN":
            condition_level += 1
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{starting_x + 18}",
                "y": f"{start_y_offset + 18}"
            })

            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{starting_x + 18}",
                "y": f"{split_line - condition_level*(18)}"
            })

            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{connection_x + 18}",
                "y": f"{split_line - condition_level*(18)}"
            })

            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{connection_x + 18}",
                "y": f"{con_y_offset+ 18}"
            })
        # Starting Waypoint
        elif starting_y > connection_y:
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{starting_x_offset}",
                "y": f"{start_y_offset}"
            })

            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{starting_x_offset}",
                "y": f"{con_y_offset}"
            })

            # Ending Waypoint
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{connection_x}",
                "y": f"{con_y_offset}"
            })
        elif starting_y < (connection_y - 9):
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{starting_x_offset}",
                "y": f"{start_y_offset}"
            })
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{connection_x + 18}",
                "y": f"{start_y_offset}"
            })
            # Ending Waypoint
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{connection_x + 18}",
                "y": f"{con_y_offset - 18}"
            })
        else:
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{starting_x_offset}",
                "y": f"{start_y_offset}"
            })
            # Ending Waypoint
            ET.SubElement(edge, f"{{{di_ns}}}waypoint", {
                "x": f"{connection_x}",
                "y": f"{con_y_offset}"
            })


def add_draw_dimension():
    skip_list = []
    last_dimension = 0
    for x in bpmn_elements_list:
       # bpmn_elements_list[x]["dimension"] = 0
        if "StartEvent" in x:
            bpmn_elements_list[x]["dimension"] = 0
        else:
            if "Task_" in x and bpmn_elements_list[x]["step"] not in skip_list:
                previous_step = bpmn_elements_list[x]["step"] - 1
                prev_id = find_id_for_step(previous_step)
                while prev_id is None:
                    previous_step -= 1
                    prev_id = find_id_for_step(previous_step)

                bpmn_elements_list[x]["dimension"] = bpmn_elements_list[prev_id]["dimension"]
            elif "GW_split" in x:
                previous_step = bpmn_elements_list[x]["step"] - 1
                prev_id = find_id_for_step(previous_step)
                while prev_id is None:
                    previous_step -= 1
                    prev_id = find_id_for_step(previous_step)
                join_dimension = bpmn_elements_list[prev_id]["dimension"]
                if bpmn_elements_list[x]["step"] not in skip_list:
                    bpmn_elements_list[x]["dimension"] = bpmn_elements_list[prev_id]["dimension"]
                elif bpmn_elements_list[x]["step"] in skip_list:
                    join_dimension = bpmn_elements_list[x]["dimension"]
                if "GW_split_para" in x:
                    parallels = list(bpmn_elements_list[x]["parallel_steps"])
                    starting_dim = join_dimension
                    dimensions_add = len(parallels) + starting_dim - 1
                    dimension_ink = bpmn_elements_list[x]["dimension"]
                    for p in parallels:
                        skip_list.append(p)
                        if isinstance(p, int):
                            id_para = find_id_for_step(p)
                        else:
                            id_para = p
                        bpmn_elements_list[id_para]["dimension"] = dimensions_add
                        dimensions_add -= 1
                elif "GW_split_switch" in x:
                    cases = list(bpmn_elements_list[x]["cases"])
                    dimension_ink = bpmn_elements_list[x]["dimension"]
                    starting_dim = join_dimension
                    dimensions_add = len(cases) + starting_dim - 1
                    for p in cases:
                        if isinstance(p,int):
                            skip_list.append(p)
                            id_para = find_id_for_step(p)
                        else:
                            skip_list.append(bpmn_elements_list[p]["step"])
                            id_para = p
                        bpmn_elements_list[id_para]["dimension"] = dimensions_add
                        dimensions_add -= 1
            elif "GW_join" in x:
                split_id = bpmn_elements_list[x]["split"]
                bpmn_elements_list[x]["dimension"] = bpmn_elements_list[split_id]["dimension"]

            elif "EndEvent" in x:
                bpmn_elements_list[x]["dimension"] = 0

# --------------------------------------------------------------------------------
# Load your JSON (example snippet here)
filename = 'input_playbook.json'
directory_path = Path("Input")

for json_file in directory_path.glob("*.json"):
    # IMPORTANT: Reassign the global variables
    print(json_file)
    bpmn_elements_list = {}
    sequence_flow_list = {}
    parallel_levels = {}
    level_counter = 1
    join_list = []
    condition_level = 0
    with open(json_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing {json_file}: {e}")
            continue
        print(f"Transforming {json_file.name}")

        id_name = json_file.name[:-5]

       # try:
            # ------------------------------------------------------
            # Register namespaces for pretty output
        ET.register_namespace("bpmn", "http://www.omg.org/spec/BPMN/20100524/MODEL")
        ET.register_namespace("bpmndi", "http://www.omg.org/spec/BPMN/20100524/DI")
        ET.register_namespace("dc", "http://www.omg.org/spec/DD/20100524/DC")
        ET.register_namespace("di", "http://www.omg.org/spec/DD/20100524/DI")
        ET.register_namespace("camunda", "http://camunda.org/schema/1.0/bpmn")
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

        # Create root <bpmn:definitions>
        definitions = ET.Element("{http://www.omg.org/spec/BPMN/20100524/MODEL}definitions", {
            "id": f"Definitions_{id_name}",
            "targetNamespace": "http://bpmn.io/schema/bpmn"
        })

        # Create <bpmn:process> and append it to <bpmn:definitions>
        bpmn_ns = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        process = ET.SubElement(definitions, f"{{{bpmn_ns}}}process", {"id": f"Process_{id_name}", "isExecutable": "true"})
        dc_ns = "http://www.omg.org/spec/DD/20100524/DC"
        di_ns = "http://www.omg.org/spec/DD/20100524/DI"
        playbook_steps_list = data['extracted_playbook']
        #print(playbook_steps_list)
        #print("\n")
        # Extract Process Logic
        add_elements(playbook_steps_list)
        print(bpmn_elements_list)
        enrich_bpmn_elements()
        print(f"Enriched: {bpmn_elements_list}")
        print("\n")
        add_draw_dimension()
        add_sequence_flow()
        print(sequence_flow_list)
        print("\n")

        #print(bpmn_elements_list)
        # Create Diagram
        bpmndi_ns = "http://www.omg.org/spec/BPMN/20100524/DI"
        diagram = ET.SubElement(definitions, f"{{{bpmndi_ns}}}BPMNDiagram", {"id": f"Diagram_{id_name}"})
        plane = ET.SubElement(diagram, f"{{{bpmndi_ns}}}BPMNPlane", {"id": f"Plane_{id_name}", "bpmnElement": f"Process_{id_name}" })
        # List for the x,y values, anchor points
        # add to sequence flow x-source, y-source; x-target, y-target
        #sorted_for_draw = sort_elements()

        coordinates_list = calculate_coordinates.write_BPMNShapes(bpmn_elements_list, sequence_flow_list)
        draw_elements()
        write_BPMNEdges()

        rough_string = ET.tostring(definitions, encoding="utf-8")
        # Use minidom to pretty-print it
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")
        # Write the pretty XML to file
        output_path = Path("Output")
        output_name = f"Output/{id_name}.bpmn"
        with open(output_name, "w", encoding="utf-8") as f:
            f.write(pretty_xml)


       # print("\n")
       # print(f"Parallel Levels: \n {parallel_levels}")
       # print("\n")
        print(f"Coordinates: \n {coordinates_list}")
       # print("\n")
   #     shutil.copy2(json_file, "working")
   #     print("Playbook was moved")
       # shutil.copy2(f"{json_file}", "not_working")



#tree.write("output.bpmn", encoding="utf-8", xml_declaration=True)