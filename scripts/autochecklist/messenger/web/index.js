eel.expose(set_title);
function set_title(title) {
    // TODO: Implement this
    console.log(`set_title("${title}")`);
}

eel.expose(set_description);
function set_description(description) {
    // TODO: Implement this
    console.log(`set_description("${description}")`);
}

eel.expose(log_status);
function log_status(task_name, index, status, message) {
    // TODO: Implement this
    console.log(`log_status("${task_name}", ${index}, "${status}", "${message}")`);
}

eel.expose(log_problem);
function log_problem(task_name, level, message) {
    // TODO: Implement this
    console.log(`log_problem("${task_name}", "${level}", "${message}")`);
}

eel.expose(show_bool_input_dialog);
function show_bool_input_dialog(key, prompt, title) {
    // TODO: Implement this
    console.log(`show_bool_input_dialog(${key}, "${prompt}", "${title}")`);
    eel.handle_bool_input(key, true);
}

eel.expose(show_input_dialog);
function show_input_dialog(key, title, prompt, params) {
    // TODO: Implement this
    console.log(`show_input_dialog(${key}, "${title}", "${prompt}", ${JSON.stringify(params)})`);
    let inputs = {};
    for (const name in params) {
        inputs[name] = name == "pizza_topping" ? "pineapple" : "123";
    }
    console.log(inputs);
    eel.handle_input(key, inputs);
}

eel.expose(add_action_item);
function add_action_item(task_name, index, prompt, allowed_responses) {
    // TODO: Implement this
    console.log(`add_action_item("${task_name}", ${index}, "${prompt}", [${allowed_responses.map((x) => `"${x}"`)}])`);
    eel.handle_user_action(task_name, "DONE");
}

eel.expose(add_command);
function add_command(task_name, command_name) {
    // TODO: Implement this
    console.log(`add_command("${task_name}", "${command_name}")`);
    eel.handle_command(task_name, command_name);
}

eel.expose(remove_command);
function remove_command(task_name, command_name) {
    // TODO: Implement this
    console.log(`remove_command("${task_name}", "${command_name}")`);
}

eel.expose(show_script_done_message);
function show_script_done_message() {
    // TODO: Implement this
    console.log("show_script_done_message()");
}

eel.expose(create_progress_bar);
function create_progress_bar(display_name, max_value, units) {
    // TODO: Implement this
    console.log(`create_progress_bar("${display_name}", ${max_value}, "${units}")`);
    return get_unique_key();
}

eel.expose(update_progress_bar);
function update_progress_bar(key, progress) {
    // TODO: Implement this
    console.log(`update_progress_bar(${key}, ${progress})`);
}

eel.expose(delete_progress_bar);
function delete_progress_bar(key) {
    // TODO: Implement this
    console.log(`delete_progress_bar(${key})`);
}

const key_generation_array = new Uint32Array([0]);
/*
 * Returns an integer that can be used as a unique identifier. Calling this
 * function multiple times will not produce the same value.
 */
function get_unique_key() {
    return Atomics.add(key_generation_array, 0, 1);
}
