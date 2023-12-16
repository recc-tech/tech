console.log("Hello from index.js!");
console.log(eel);

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

eel.expose(input_str);
function input_str(display_name, password, prompt, title, error_message) {
    // TODO: Implement this
    console.log(`input_str("${display_name}", ${password}, "${prompt}", "${title}", "${error_message}")`);
    eel.handle_input_str("1");
}

eel.expose(show_bool_input_dialog);
function show_bool_input_dialog(prompt, title) {
    // TODO: Implement this
    console.log(`show_bool_input_dialog("${prompt}", "${title}")`);
    eel.handle_bool_input(true);
}

eel.expose(show_input_dialog);
function show_input_dialog(title, prompt, params) {
    // TODO: Implement this
    console.log(`show_input_dialog("${title}", "${prompt}", ${JSON.stringify(params)})`);
    let output = {};
    for (const name in params) {
        output[name] = "123";
    }
    console.log(output);
    eel.handle_input(output);
}

eel.expose(add_action_item);
function add_action_item(task_name, index, prompt, allow_retry) {
    // TODO: Implement this
    console.log(`add_action_item("${task_name}", ${index}, "${prompt}", ${allow_retry})`);
    eel.handle_user_action(task_name, "DONE");
}

eel.expose(remove_action_item);
function remove_action_item(task_name) {
    // TODO: Implement this
    console.log(`remove_action_item("${task_name}")`);
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
