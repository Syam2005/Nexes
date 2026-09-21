// NEXUS Demo File — ES5 JavaScript legacy patterns
var apiUrl = "https://api.example.com";
var users = [];

// Old-style function declarations
function fetchUsers(callback) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", apiUrl + "/users");
    xhr.onreadystatechange = function() {
        if (xhr.readyState == 4 && xhr.status == 200) {
            callback(JSON.parse(xhr.responseText));
        }
    };
    xhr.send();
}

// Promise chains instead of async/await
function getUser(id) {
    return fetch(apiUrl + "/users/" + id)
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            return data;
        });
}

// String concatenation
function buildMessage(user, action) {
    return "User " + user.name + " performed " + action + " at " + new Date();
}

// var instead of const/let
var config = {
    timeout: 5000,
    retries: 3
};

// == instead of ===
function isAdmin(user) {
    if (user.role == "admin" || user.role == null) {
        return true;
    }
    return false;
}

// Old forEach with function
var ids = [1, 2, 3, 4, 5];
ids.forEach(function(id) {
    console.log("Processing: " + id);
});

// Object.assign instead of spread
var defaults = {color: "blue", size: "medium"};
var options = Object.assign({}, defaults, {color: "red"});