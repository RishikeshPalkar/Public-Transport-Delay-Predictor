package com.sbb.predictor.service;

import com.sbb.predictor.model.Trip;
import com.sbb.predictor.model.WeatherObservation;
import com.sbb.predictor.repository.TripRepository;
import com.sbb.predictor.repository.WeatherRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class DashboardService {

    @Autowired
    private WeatherRepository weatherRepository;

    @Autowired
    private TripRepository tripRepository;

    @Autowired
    private MlClientService mlClientService;

    public Map<String, Object> getDashboardData(String stationUic) {
        Map<String, Object> result = new HashMap<>();

        // 1. Fetch Latest Weather
        Optional<WeatherObservation> weatherOpt = weatherRepository.findFirstByStationUicOrderByObservationTimeDesc(stationUic);
        Map<String, Object> weatherMap = new HashMap<>();
        if (weatherOpt.isPresent()) {
            WeatherObservation w = weatherOpt.get();
            weatherMap.put("temperature_c", w.getTemperatureC() != null ? w.getTemperatureC() : 15.0);
            weatherMap.put("precipitation_mm", w.getPrecipitationMm() != null ? w.getPrecipitationMm() : 0.0);
            weatherMap.put("snow_depth_cm", w.getSnowDepthCm() != null ? w.getSnowDepthCm() : 0.0);
            weatherMap.put("weather_code", w.getWeatherCode() != null ? w.getWeatherCode() : 0);
        } else {
            weatherMap.put("temperature_c", 15.0);
            weatherMap.put("precipitation_mm", 0.0);
            weatherMap.put("snow_depth_cm", 0.0);
            weatherMap.put("weather_code", 0);
        }
        result.put("weather", weatherMap);

        Double temp = (Double) weatherMap.get("temperature_c");
        Double precip = (Double) weatherMap.get("precipitation_mm");
        Double snow = (Double) weatherMap.get("snow_depth_cm");
        Integer wCode = (Integer) weatherMap.get("weather_code");

        // 2. Process Departures
        List<Trip> depTrips = tripRepository.findTop10ByStationUicAndScheduledDepartureIsNotNullAndDepartureDelayMinIsNotNullOrderByScheduledDepartureDesc(stationUic);
        List<Map<String, Object>> departures = new ArrayList<>();
        for (Trip trip : depTrips) {
            Map<String, Object> item = new HashMap<>();
            item.put("scheduled_time", trip.getScheduledDeparture().toString());
            item.put("linien_text", trip.getLinienText());

            // Destination lookup
            Optional<Trip> destTrip = tripRepository.findFirstByFahrtBezeichnerAndBetriebstagAndScheduledArrivalIsNotNullOrderByScheduledArrivalDesc(
                    trip.getFahrtBezeichner(), trip.getBetriebstag());
            String destination = destTrip.map(Trip::getStationName).orElse("Unknown Destination");
            item.put("route", destination);

            // Predict departure delay via ML FastAPI Client
            Double predictedDelay = mlClientService.predictDeparture(
                    stationUic,
                    trip.getLinienText(),
                    trip.getScheduledDeparture().toString(),
                    temp, precip, snow, wCode
            );
            item.put("predicted_delay_min", predictedDelay);

            departures.add(item);
        }
        result.put("departures", departures);

        // 3. Process Arrivals
        List<Trip> arrTrips = tripRepository.findTop10ByStationUicAndScheduledArrivalIsNotNullAndArrivalDelayMinIsNotNullOrderByScheduledArrivalDesc(stationUic);
        List<Map<String, Object>> arrivals = new ArrayList<>();
        for (Trip trip : arrTrips) {
            Map<String, Object> item = new HashMap<>();
            item.put("scheduled_time", trip.getScheduledArrival().toString());
            item.put("linien_text", trip.getLinienText());

            // Origin lookup
            Optional<Trip> origTrip = tripRepository.findFirstByFahrtBezeichnerAndBetriebstagAndScheduledDepartureIsNotNullOrderByScheduledDepartureAsc(
                    trip.getFahrtBezeichner(), trip.getBetriebstag());
            String origin = origTrip.map(Trip::getStationName).orElse("Unknown Origin");
            item.put("route", origin);

            // Fetch Origin Departure Delay for arrival prediction
            Double originDelay = origTrip.map(t -> t.getDepartureDelayMin() != null ? t.getDepartureDelayMin() : 0.0).orElse(0.0);

            // Predict arrival delay via ML FastAPI Client
            Double predictedDelay = mlClientService.predictArrival(
                    stationUic,
                    trip.getLinienText(),
                    trip.getScheduledArrival().toString(),
                    temp, precip, snow, wCode,
                    originDelay
            );
            item.put("predicted_delay_min", predictedDelay);

            arrivals.add(item);
        }
        result.put("arrivals", arrivals);

        return result;
    }
}
