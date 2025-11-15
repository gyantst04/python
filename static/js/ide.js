let editor;

window.onload =function(){
    editor = ace.edit("editor");
    editor.setTheme("ace/theme/monokai");
    editor.session.setMode("ace/mode/python");

    // enable auto completions

    ace.require("ace/ext/language_tools");
    editor.setOptions({
        enableBasicAutoCompletion: true,
        enableSnippets:true,
        enableLiveAutoCompletion:true,
        fontSize: "14pt",
        tabSize:4,
        useSoftTabs:true
    });
}