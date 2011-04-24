function subscribe(channel, handleMessage){
  var _this = this;
  this.errorSleepTime = 500; 
  channel = "/subscribe/" + channel;
  msg_id = null;
  handleMessage = handleMessage;
  poll = function() {
  var args = {"_xsrf": getCookie("_xsrf")};     
  if (msg_id) args.msg_id = msg_id;   
  $.ajax({url: channel, type: "POST", dataType: "text",
          data: $.param(args), success: onSuccess,
          error: onError});
  };
  onSuccess = function(response) {
    try {
        newMessages(eval("(" + response + ")"));
    } catch (e) {
        onError();
        return;
    }
    _this.errorSleepTime = 500;
    window.setTimeout(poll, 0);
  }

  onError = function(response) {
    _this.errorSleepTime *= 2;
    console.log("Poll error; sleeping for", _this.errorSleepTime, "ms");
    window.setTimeout(poll, _this.errorSleepTime);
  }

  newMessages = function(response) {
    if (!response.messages) return;
    var messages = response.messages;
    msg_id = messages[messages.length - 1].msg_id;
    for (var i = 0; i < messages.length; i++) {
        handleMessage(messages[i]);
    }
  }
  poll();
  
};  