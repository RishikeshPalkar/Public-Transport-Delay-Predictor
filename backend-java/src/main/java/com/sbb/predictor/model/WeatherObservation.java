package com.sbb.predictor.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "weather_observations")
public class WeatherObservation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "station_uic", length = 20, nullable = false)
    private String stationUic;

    @Column(name = "observation_time", nullable = false)
    private LocalDateTime observationTime;

    @Column(name = "temperature_c")
    private Double temperatureC;

    @Column(name = "precipitation_mm")
    private Double precipitationMm;

    @Column(name = "snow_depth_cm")
    private Double snowDepthCm;

    @Column(name = "weather_code")
    private Integer weatherCode;

    public WeatherObservation() {}

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public String getStationUic() {
        return stationUic;
    }

    public void setStationUic(String stationUic) {
        this.stationUic = stationUic;
    }

    public LocalDateTime getObservationTime() {
        return observationTime;
    }

    public void setObservationTime(LocalDateTime observationTime) {
        this.observationTime = observationTime;
    }

    public Double getTemperatureC() {
        return temperatureC;
    }

    public void setTemperatureC(Double temperatureC) {
        this.temperatureC = temperatureC;
    }

    public Double getPrecipitationMm() {
        return precipitationMm;
    }

    public void setPrecipitationMm(Double precipitationMm) {
        this.precipitationMm = precipitationMm;
    }

    public Double getSnowDepthCm() {
        return snowDepthCm;
    }

    public void setSnowDepthCm(Double snowDepthCm) {
        this.snowDepthCm = snowDepthCm;
    }

    public Integer getWeatherCode() {
        return weatherCode;
    }

    public void setWeatherCode(Integer weatherCode) {
        this.weatherCode = weatherCode;
    }
}
