package com.sbb.predictor.controller;

import com.sbb.predictor.model.Station;
import com.sbb.predictor.repository.StationRepository;
import com.sbb.predictor.service.DashboardService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*") // Allow requests from any frontend port/domain
public class DashboardController {

    @Autowired
    private StationRepository stationRepository;

    @Autowired
    private DashboardService dashboardService;

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> getHealth() {
        return ResponseEntity.ok(Map.of("status", "HEALTHY"));
    }

    @GetMapping("/stations")
    public ResponseEntity<List<Station>> getAllStations() {
        List<Station> stations = stationRepository.findAll();
        return ResponseEntity.ok(stations);
    }

    @GetMapping("/dashboard/data")
    public ResponseEntity<Map<String, Object>> getDashboardData(@RequestParam("station_uic") String stationUic) {
        Map<String, Object> data = dashboardService.getDashboardData(stationUic);
        return ResponseEntity.ok(data);
    }
}
