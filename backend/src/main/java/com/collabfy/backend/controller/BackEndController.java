package com.collabfy.backend.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class BackEndController {

    @GetMapping("/api/test")
    public String testEndpoint() {
        return "Hello from the Back End!";
    }
}
