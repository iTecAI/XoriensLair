function command (command, data, port, callback) {
    console.log('Sending POST');
    var sendData = {
        "command":command,
        "kwargs":data
    };
    var len = sendData.toString().length;
    $.post(
        'http://' + self.location.hostname + ':' + port.toString(),
        sendData,
        callback,
        'json'
    );
}