package com.sbb.predictor.model;

import jakarta.persistence.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "trips")
public class Trip {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "betriebstag", nullable = false)
    private LocalDate betriebstag;

    @Column(name = "fahrt_bezeichner", length = 100, nullable = false)
    private String fahrtBezeichner;

    @Column(name = "produkt_id", length = 20)
    private String produktId;

    @Column(name = "linien_text", length = 50)
    private String linienText;

    @Column(name = "station_uic", length = 20, nullable = false)
    private String stationUic;

    @Column(name = "station_name", length = 100, nullable = false)
    private String stationName;

    @Column(name = "scheduled_arrival")
    private LocalDateTime scheduledArrival;

    @Column(name = "actual_arrival")
    private LocalDateTime actualArrival;

    @Column(name = "arrival_delay_min")
    private Double arrivalDelayMin;

    @Column(name = "scheduled_departure")
    private LocalDateTime scheduledDeparture;

    @Column(name = "actual_departure")
    private LocalDateTime actualDeparture;

    @Column(name = "departure_delay_min")
    private Double departureDelayMin;

    @Column(name = "faellt_aus")
    private Boolean faelltAus;

    @Column(name = "zusatzfahrt")
    private Boolean zusatzfahrt;

    public Trip() {}

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public LocalDate getBetriebstag() {
        return betriebstag;
    }

    public void setBetriebstag(LocalDate betriebstag) {
        this.betriebstag = betriebstag;
    }

    public String getFahrtBezeichner() {
        return fahrtBezeichner;
    }

    public void setFahrtBezeichner(String fahrtBezeichner) {
        this.fahrtBezeichner = fahrtBezeichner;
    }

    public String getProduktId() {
        return produktId;
    }

    public void setProduktId(String produktId) {
        this.produktId = produktId;
    }

    public String getLinienText() {
        return linienText;
    }

    public void setLinienText(String linienText) {
        this.linienText = linienText;
    }

    public String getStationUic() {
        return stationUic;
    }

    public void setStationUic(String stationUic) {
        this.stationUic = stationUic;
    }

    public String getStationName() {
        return stationName;
    }

    public void setStationName(String stationName) {
        this.stationName = stationName;
    }

    public LocalDateTime getScheduledArrival() {
        return scheduledArrival;
    }

    public void setScheduledArrival(LocalDateTime scheduledArrival) {
        this.scheduledArrival = scheduledArrival;
    }

    public LocalDateTime getActualArrival() {
        return actualArrival;
    }

    public void setActualArrival(LocalDateTime actualArrival) {
        this.actualArrival = actualArrival;
    }

    public Double getArrivalDelayMin() {
        return arrivalDelayMin;
    }

    public void setArrivalDelayMin(Double arrivalDelayMin) {
        this.arrivalDelayMin = arrivalDelayMin;
    }

    public LocalDateTime getScheduledDeparture() {
        return scheduledDeparture;
    }

    public void setScheduledDeparture(LocalDateTime scheduledDeparture) {
        this.scheduledDeparture = scheduledDeparture;
    }

    public LocalDateTime getActualDeparture() {
        return actualDeparture;
    }

    public void setActualDeparture(LocalDateTime actualDeparture) {
        this.actualDeparture = actualDeparture;
    }

    public Double getDepartureDelayMin() {
        return departureDelayMin;
    }

    public void setDepartureDelayMin(Double departureDelayMin) {
        this.departureDelayMin = departureDelayMin;
    }

    public Boolean getFaelltAus() {
        return faelltAus;
    }

    public void setFaelltAus(Boolean faelltAus) {
        this.faelltAus = faelltAus;
    }

    public Boolean getZusatzfahrt() {
        return zusatzfahrt;
    }

    public void setZusatzfahrt(Boolean zusatzfahrt) {
        this.zusatzfahrt = zusatzfahrt;
    }
}
