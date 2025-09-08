import math

# Shapa Sizes
TASK_HEIGHT = 56
TASK_WIDTH = 100
SCRIPT_TASK_HEIGHT = 80
GATEWAY_HEIGHT = 36
GATEWAY_WIDTH = 36
BUFFER_HORIZONTAL = 50
BUFFER_VERTICAL = 30
DRAW_PADDING_Y = 100
DRAW_PADDING_X = 80


def calculate_offset(old_y, type):
    new_y = old_y
    if type == "CONDITION_SPLIT" or type == "CONDITION_JOIN" or type == "PARALLEL_SPLIT" or type == "PARALLEL_JOIN" or type == "SWITCH_SPLIT" or type == "SWITCH_JOIN":
        new_y += 18
    elif type == "StartEvent" or type == "EndEvent":
        new_y += 18
    else:
        new_y += 28

    return new_y


def calculate_x_offset(old_x, type):
    new_x = old_x
    if type == "CONDITION_SPLIT" or type == "CONDITION_JOIN" or type == "PARALLEL_SPLIT" or type == "PARALLEL_JOIN" or type == "SWITCH_SPLIT" or type == "SWITCH_JOIN":
        new_x += 36
    elif type == "StartEvent":
        new_x += 36
    else:
        new_x += 100
    return new_x


def calculate_dimensions(bpmn_elements_list, sequence_flow_list):
    amount_tasks = 0
    amount_gateways = 0
    # placeholder for every edge (edge width)
    amount_blanks = 0
    parallels = 0
    cases = 0
    for el in bpmn_elements_list:
        if bpmn_elements_list[el]["type"] == "StartEvent" or bpmn_elements_list[el]["type"] == "EndEvent":
            amount_gateways += 1
        elif bpmn_elements_list[el]["type"] == 'PARALLEL_SPLIT' or bpmn_elements_list[el]["type"] == 'PARALLEL_JOIN':
            amount_gateways += 1
        elif bpmn_elements_list[el]["type"] == 'CONDITION_SPLIT' or bpmn_elements_list[el]["type"] == 'CONDITION_JOIN':
            amount_gateways += 1
        elif bpmn_elements_list[el]["type"] == 'ACTION':
            amount_tasks += 1

    unique_sources = {v['source'] for v in sequence_flow_list.values()}
    amount_blanks = len(unique_sources)

    dimensions_x = BUFFER_HORIZONTAL*amount_blanks + amount_gateways*GATEWAY_WIDTH + amount_tasks*TASK_WIDTH

    dimensions_y = 1000

    dimensions = {"estimate_x": dimensions_x, "estimate_y": dimensions_y}
    print(f"Dimensions: {dimensions}")
    CENTRAL_AXIS = math.ceil(DRAW_PADDING_Y + dimensions_y / 2)
    return dimensions, CENTRAL_AXIS


def calculate_shape_coordinates(bpmn_elements_list, id, x_dim, last_y, CENTRAL_AXIS, amount, even, index):
    type = bpmn_elements_list[id]["type"]
    position = index +1
    y = 0
    width = 0
    height = 0
    if type == "ACTION":
        width = TASK_WIDTH
        height = TASK_HEIGHT
    else:
        width = GATEWAY_WIDTH
        height = GATEWAY_HEIGHT
    if amount > 1:
        if even:
            upper_middle = math.floor(amount/2)
            lower_middle = math.ceil(amount/2)+1
            if position == upper_middle:
                y = CENTRAL_AXIS - 34
            elif position == lower_middle:
                y = CENTRAL_AXIS + 34
            elif position < upper_middle:
                # Hier minus
                y = (CENTRAL_AXIS-60) - ((upper_middle-position)*60)
            elif position > lower_middle:
                y = (CENTRAL_AXIS+60) + ((position-lower_middle)*60)
        else:
            middle_position = round(amount/2)
            if position == middle_position:
                y = CENTRAL_AXIS
            elif position < middle_position:
                # y = CENTRAL_AXIS + (60 * (middle_position + (middle_position - position)))
                y = CENTRAL_AXIS - (60*(middle_position-position))
            elif position > middle_position:
               # y = CENTRAL_AXIS + (60 * (middle_position - position))
                y = CENTRAL_AXIS + (60*(middle_position+(middle_position-position)))
    else:
        y = CENTRAL_AXIS

    if "GW_" in id or "StartEvent" in id or "EndEvent" in id:
        y += 9
    coordinates = {"x":x_dim,"y":y,"width":width,"height":height}
    new_y = CENTRAL_AXIS
    return coordinates, new_y


def find_id_for_step(i, bpmn_elements_list):
    step_number = i
    if isinstance(step_number, int):
        for key, value in bpmn_elements_list.items():
            if value.get('step') == step_number:
                return key
    elif isinstance(step_number, float):
        for key, value in bpmn_elements_list.items():
            if value.get('step') == step_number:
                return key
    else:
        return None


def write_BPMNShapes(bpmn_elements, sequenceflowlist):
    offsets = {"StartEvent": 36, "EndEvent": 36, }
    coordinates_list = {}
    dimensions, CENTRAL_AXIS = calculate_dimensions(bpmn_elements,sequenceflowlist)
    print(dimensions)
    last_x = DRAW_PADDING_X
    last_y = CENTRAL_AXIS
    # List with column separated elements
    #sorted_bpmn_list = dict(sorted(bpmn_elements_list.items(), key=lambda item: item[1]["step"]))

    print(bpmn_elements)
    for i in bpmn_elements:
        dimension = bpmn_elements[i]["dimension"]
        y = last_y - (TASK_HEIGHT*dimension) - dimension*35
        if "GW_" in i:
            coordinates_list[i] = {"x": last_x, "y": y + GATEWAY_HEIGHT/4, "width": GATEWAY_WIDTH, "height": GATEWAY_HEIGHT}
            last_x += 70
        elif "Event" in i:
            coordinates_list[i] = {"x": last_x, "y": y + 9, "width": 36, "height": 36}
            last_x += 70
        else:
            coordinates_list[i] = {"x": last_x ,"y": y, "width": TASK_WIDTH, "height":TASK_HEIGHT}
            last_x += 150


    skip_list = []
    for i in bpmn_elements:
        step = bpmn_elements[i]["step"]
        type = bpmn_elements[i]["type"]
        id = i
        if type != "StartEvent" and type != "EndEvent":
            if isinstance(step, float):
                previous_step = step - 0.5
                prev_id = find_id_for_step(int(previous_step), bpmn_elements)
                while prev_id is None:
                    previous_step -= 0.5
                    remainder = previous_step % 1
                    if remainder == 0.0:
                        previous_step = int(previous_step)
                    prev_id = find_id_for_step(previous_step, bpmn_elements)
            else:
                previous_step = step - 1
                prev_id = find_id_for_step(previous_step, bpmn_elements)
                while prev_id is None:
                    previous_step -= 0.5
                    remainder = previous_step % 1
                    if remainder == 0.0:
                        previous_step = int(previous_step)
                    prev_id = find_id_for_step(previous_step, bpmn_elements)

            last_x = coordinates_list[prev_id]["x"]


            if isinstance(step, float):
                next_step = math.ceil(step)
                next_id = find_id_for_step(next_step, bpmn_elements)
                while next_id is None:
                    next_step += 0.5
                    next_id = find_id_for_step(next_step, bpmn_elements)
                skip_list.append(next_step)
                temp_offset = 0
                if "GW_" in prev_id:
                    temp_offset += 70
                else:
                    temp_offset += 150
                if "GW_" in id:
                    coordinates_list[next_id]["x"] = last_x + 70 + temp_offset
                else:
                    coordinates_list[next_id]["x"] = last_x + 150 + temp_offset
            if step not in skip_list:
                if "GW_" in prev_id:
                    coordinates_list[i]["x"] = last_x + 70
                    current_x = last_x + 70
                elif "Event" in prev_id:
                    coordinates_list[i]["x"] = last_x + 70
                else:
                    coordinates_list[i]["x"] = last_x + 150
            if "GW_split" in id:
                current_x = coordinates_list[id]["x"]
                if "switch" in id:
                    cases = bpmn_elements[id]["cases"]
                    for c in cases:
                        next_id = find_id_for_step(c, bpmn_elements)
                        skip_list.append(c)
                        coordinates_list[next_id]["x"] = current_x + 70
                elif "para" in id:
                    parallels = bpmn_elements[id]["parallel_steps"]
                    for p in parallels:
                        next_id = find_id_for_step(p, bpmn_elements)
                        skip_list.append(p)
                        coordinates_list[next_id]["x"] = current_x + 70
        if type == "EndEvent":
            keys = list(coordinates_list.keys())
            second_last_key = keys[-2]
            coordinates_list["EndEvent"]["x"] = coordinates_list[second_last_key]["x"] + 150


    return coordinates_list