eel.expose(set_title);
/**
 * Set the title of the whole page.
 *
 * @param {string} title - The new title.
 */
function set_title(title) {
    // TODO: Implement this
    console.log(`set_title("${title}")`);
}

eel.expose(set_description);
/**
 * Set the description for the current script.
 *
 * @param {string} description - The new description.
 */
function set_description(description) {
    // TODO: Implement this
    console.log(`set_description("${description}")`);
}

eel.expose(log_status);
/**
 * Update the status of a task.
 *
 * @param {string} task_name
 * The unique name of the task to update.
 * @param {number | null} index
 * An optional index to control the order in which the tasks are listed. Tasks
 * with lower indices should be shown first.
 * @param {string} status
 * The new status of the task. Possible values: `"NOT_STARTED"`, `"RUNNING"`,
 * `"WAITING_FOR_USER"`, `"DONE"`, `"SKIPPED"`.
 * @param {string} message
 * More details about what's currently happening.
 */
function log_status(task_name, index, status, message) {
    // TODO: Implement this
    console.log(
        `log_status("${task_name}", ${index}, "${status}", "${message}")`);
}

eel.expose(log_problem);
/**
 * Show that a problem has occurred.
 *
 * @param {string} task_name
 * The unique name of the affected task.
 * @param {string} level
 * The problem level, which indicates seriousness. Possible values in
 * increasing order of seriousness: `"WARN"`, `"ERROR"`, `"FATAL"`.
 * @param {string} message
 * More details about what went wrong.
 */
function log_problem(task_name, level, message) {
    // TODO: Implement this
    console.log(`log_problem("${task_name}", "${level}", "${message}")`);
}

eel.expose(show_bool_input_dialog);
/**
 * Create an input dialog that lets the user choose yes or no.
 *
 * @param {number} key
 * A unique number that identifies this input dialog in case multiple dialogs
 * are opened at once.
 * @param {string} prompt
 * A message explaining what input is expected.
 * @param {string} title
 * Title for the input dialog. It may be empty.
 */
function show_bool_input_dialog(key, prompt, title) {
    // TODO: Implement this
    console.log(`show_bool_input_dialog(${key}, "${prompt}", "${title}")`);
    // Once the user makes their choice, asynchronously return the value by
    // calling eel.handle_bool_input with the same key and the choice (true for
    // yes, false for no).
    eel.handle_bool_input(key, true);
}

eel.expose(show_input_dialog);
/**
 * Show an input dialog with multiple string input fields.
 *
 * @param {number} key
 * A unique number that identifies this input dialog in case multiple dialogs
 * are opened at once.
 * @param {string} title
 * Title for the input dialog. It may be empty.
 * @param {string} prompt
 * A message summarizing all the required inputs. It may be empty.
 * @param {object} params
 * Descriptions for all the input fields to show.
 * @param {string} params[].label
 * A user-friendly name for the input field.
 * @param {boolean} params[].is_password
 * Whether the input is a password.
 * @param {string} params[].description
 * An explanation of the expected input for this field. It may be empty.
 * @param {string} params[].default
 * The default input. It may be empty.
 * @param {string} params[].error_message
 * A message explaining what's wrong with the previous input. It may be empty.
 */
function show_input_dialog(key, title, prompt, params) {
    // TODO: Implement this
    console.log(
        `show_input_dialog(${key}, "${title}", "${prompt}", `
        + `${JSON.stringify(params)})`);
    // Once the user submits all the inputs, call eel.handle_input with the
    // same key and an object containing, for each input field, the display
    // name as key and the user's input as value.
    let inputs = {};
    for (const name in params) {
        inputs[name] = (name == "pizza_topping" ? "pineapple" : "123");
    }
    console.log(inputs);
    eel.handle_input(key, inputs);
}

eel.expose(add_action_item);
/**
 * Show the user that an action is required of them.
 *
 * @param {string} task_name
 * The unique name of the task for which user action is required.
 * @param {number | null} index
 * An optional index to control the order in which the tasks are listed. Tasks
 * with lower indices should be shown first.
 * @param {string} prompt
 * A message explaining what the user must do.
 * @param {[string]} allowed_responses
 * The responses that the user can give. Possible elements: `"DONE"`,
 * `"RETRY"`, `"SKIP"`.
 */
function add_action_item(task_name, index, prompt, allowed_responses) {
    // TODO: Implement this
    console.log(
        `add_action_item("${task_name}", ${index}, "${prompt}", `
        + `[${allowed_responses.map((x) => `"${x}"`)}])`);
    // Once the user makes their choice, asynchronously return the value by
    // calling eel.handle_user_action with the same task name and the choice
    // ("DONE", "RETRY", or "SKIP"). Also remove the action item immediately.
    eel.handle_user_action(task_name, "DONE");
}

eel.expose(add_command);
/**
 * Give the user the option to invoke a command (e.g., cancelling a task).
 *
 * @param {string} task_name
 * The unique name of the task that the command applies to.
 * @param {string} command_name
 * The name of the command.
 */
function add_command(task_name, command_name) {
    // TODO: Implement this
    console.log(`add_command("${task_name}", "${command_name}")`);
    // If the user wants to invoke the command, call eel.handle_command with
    // the same task and command names.
    eel.handle_command(task_name, command_name);
}

eel.expose(remove_command);
/**
 * Remove a previously-added command.
 *
 * @param {string} task_name
 * The unique name of the task that the command applies to.
 * @param {string} command_name
 * The name of the command.
 */
function remove_command(task_name, command_name) {
    // TODO: Implement this
    console.log(`remove_command("${task_name}", "${command_name}")`);
}

eel.expose(show_script_done_message);
/**
 * Show a message to say that the script is finished and that the user can
 * close the window.
 */
function show_script_done_message() {
    // TODO: Implement this
    console.log("show_script_done_message()");
}

eel.expose(create_progress_bar);
/**
 * Create a new progress bar. Returns a key that can be used to refer to this
 * progress bar for subsequent operations.
 *
 * @param {string} display_name
 * A user-friendly name for the progress bar.
 * @param {number} max_value
 * The maximum value that the progress can take.
 * @param {string} units
 * The units in which the progress is expressed (e.g., MB). It may be empty.
 * @returns {number}
 */
function create_progress_bar(display_name, max_value, units) {
    // TODO: Implement this
    console.log(
        `create_progress_bar("${display_name}", ${max_value}, "${units}")`);
    return get_unique_key();
}

eel.expose(update_progress_bar);
/**
 * Update the progress for an existing progress bar.
 *
 * @param {number} key
 * The key returned by `create_progress_bar` that identifies the progress bar.
 * @param {number} progress
 * The new progress value.
 */
function update_progress_bar(key, progress) {
    // TODO: Implement this
    console.log(`update_progress_bar(${key}, ${progress})`);
}

eel.expose(delete_progress_bar);
/**
 * Delete a progress bar.
 *
 * @param {number} key
 * The key returned by `create_progress_bar` that identifies the progress bar.
 */
function delete_progress_bar(key) {
    // TODO: Implement this
    console.log(`delete_progress_bar(${key})`);
}

const key_generation_array = new Uint32Array([0]);
/**
 * Generate an integer that can be used as a unique identifier. Calling this
 * function multiple times will not produce the same value.
 *
 * @returns {number}
 */
function get_unique_key() {
    return Atomics.add(key_generation_array, 0, 1);
}
