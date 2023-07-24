const consoleLog = document.getElementById('consoleLog');

const atBottom = () => {
    return consoleLog.scrollTop + consoleLog.clientHeight >= consoleLog.scrollHeight;
};

const addLog = (msg, level, prefix) => {
    let wasAtBottom = atBottom();

    const div = document.createElement('div');
    div.className = `log-${level}`;
    div.textContent = `[${prefix || level.toUpperCase()}] ${msg}`;

    consoleLog.append(div);

    if (wasAtBottom) consoleLog.scrollTop = consoleLog.scrollHeight;
};

addLog("Navigation Control Board Started - " + new Date().toISOString(), 'info');

const socket = io();

socket.on('log', (data) => {
    addLog(data.msg, data.level, data.prefix);
});