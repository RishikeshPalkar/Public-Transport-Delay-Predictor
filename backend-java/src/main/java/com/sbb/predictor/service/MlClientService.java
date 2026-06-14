package com.sbb.predictor.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Service
public class MlClientService {

    @Value("${ml.service.url}")
    private String mlServiceUrl;

    private final RestTemplate restTemplate = new RestTemplate();

    public Double predictDeparture(String stationUic, String linienText, String scheduledTime,
                                   Double temp, Double precip, Double snow, Integer wCode) {
        String url = mlServiceUrl + "/predict/departure";
        
        Map<String, Object> request = new HashMap<>();
        request.put("station_uic", stationUic);
        request.put("linien_text", linienText);
        request.put("scheduled_time", scheduledTime);
        request.put("temperature_c", temp);
        request.put("precipitation_mm", precip);
        request.put("snow_depth_cm", snow);
        request.put("weather_code", wCode);

        try {
            Map<String, Object> response = restTemplate.postForObject(url, request, Map.class);
            if (response != null && response.containsKey("predicted_delay_min")) {
                return ((Number) response.get("predicted_delay_min")).doubleValue();
            }
        } catch (Exception e) {
            System.err.println("[ML CLIENT ERROR] Failed to predict departure delay: " + e.getMessage());
        }
        return 0.0;
    }

    public Double predictArrival(String stationUic, String linienText, String scheduledTime,
                                 Double temp, Double precip, Double snow, Integer wCode, Double originDepartureDelay) {
        String url = mlServiceUrl + "/predict/arrival";
        
        Map<String, Object> request = new HashMap<>();
        request.put("station_uic", stationUic);
        request.put("linien_text", linienText);
        request.put("scheduled_time", scheduledTime);
        request.put("temperature_c", temp);
        request.put("precipitation_mm", precip);
        request.put("snow_depth_cm", snow);
        request.put("weather_code", wCode);
        request.put("origin_departure_delay", originDepartureDelay);

        try {
            Map<String, Object> response = restTemplate.postForObject(url, request, Map.class);
            if (response != null && response.containsKey("predicted_delay_min")) {
                return ((Number) response.get("predicted_delay_min")).doubleValue();
            }
        } catch (Exception e) {
            System.err.println("[ML CLIENT ERROR] Failed to predict arrival delay: " + e.getMessage());
        }
        return 0.0;
    }
}
