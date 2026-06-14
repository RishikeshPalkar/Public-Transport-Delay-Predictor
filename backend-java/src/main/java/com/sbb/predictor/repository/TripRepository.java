package com.sbb.predictor.repository;

import com.sbb.predictor.model.Trip;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface TripRepository extends JpaRepository<Trip, Integer> {

    // Fetch latest 10 departures for a station
    List<Trip> findTop10ByStationUicAndScheduledDepartureIsNotNullAndDepartureDelayMinIsNotNullOrderByScheduledDepartureDesc(String stationUic);

    // Fetch latest 10 arrivals for a station
    List<Trip> findTop10ByStationUicAndScheduledArrivalIsNotNullAndArrivalDelayMinIsNotNullOrderByScheduledArrivalDesc(String stationUic);

    // Find destination stop for a specific fahrt on a specific date (max scheduled_arrival)
    Optional<Trip> findFirstByFahrtBezeichnerAndBetriebstagAndScheduledArrivalIsNotNullOrderByScheduledArrivalDesc(String fahrtBezeichner, LocalDate betriebstag);

    // Find origin stop for a specific fahrt on a specific date (min scheduled_departure)
    Optional<Trip> findFirstByFahrtBezeichnerAndBetriebstagAndScheduledDepartureIsNotNullOrderByScheduledDepartureAsc(String fahrtBezeichner, LocalDate betriebstag);
}
