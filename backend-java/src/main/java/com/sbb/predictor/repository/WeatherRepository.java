package com.sbb.predictor.repository;

import com.sbb.predictor.model.WeatherObservation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface WeatherRepository extends JpaRepository<WeatherObservation, Integer> {
    Optional<WeatherObservation> findFirstByStationUicOrderByObservationTimeDesc(String stationUic);
}
