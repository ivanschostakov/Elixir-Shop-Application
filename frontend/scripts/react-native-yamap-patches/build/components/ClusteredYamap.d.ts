import React from 'react';
import { ViewProps, ImageSourcePropType, NativeSyntheticEvent } from 'react-native';
import { Animation, Point, DrivingInfo, MasstransitInfo, RoutesFoundEvent, Vehicles, CameraPosition, VisibleRegion, ScreenPoint, MapLoaded, InitialRegion, YandexLogoPosition, YandexLogoPadding } from '../interfaces';
export type ClusteredMarkerData = Record<string, unknown>;
export type ClusteredMarker<T extends ClusteredMarkerData = ClusteredMarkerData> = {
    point: Point;
    data?: T;
    iconKey?: string;
};
export type ClusteredMarkerPressEvent<T extends ClusteredMarkerData = ClusteredMarkerData> = NativeSyntheticEvent<{
    point: Point;
    data?: T;
    iconKey?: string;
}>;
export interface ClusteredYaMapProps<T extends ClusteredMarkerData = ClusteredMarkerData> extends ViewProps {
    userLocationIcon?: ImageSourcePropType;
    userLocationIconScale?: number;
    markerSize?: number;
    clusteredMarkers: ReadonlyArray<ClusteredMarker<T>>;
    markerIcons?: Record<string, ImageSourcePropType>;
    clusterColor?: string;
    showUserPosition?: boolean;
    nightMode?: boolean;
    mapStyle?: string;
    onCameraPositionChange?: (event: NativeSyntheticEvent<CameraPosition>) => void;
    onCameraPositionChangeEnd?: (event: NativeSyntheticEvent<CameraPosition>) => void;
    onMapPress?: (event: NativeSyntheticEvent<Point>) => void;
    onMapLongPress?: (event: NativeSyntheticEvent<Point>) => void;
    onMapLoaded?: (event: NativeSyntheticEvent<MapLoaded>) => void;
    onMarkerPress?: (event: ClusteredMarkerPressEvent<T>) => void;
    userLocationAccuracyFillColor?: string;
    userLocationAccuracyStrokeColor?: string;
    userLocationAccuracyStrokeWidth?: number;
    scrollGesturesEnabled?: boolean;
    zoomGesturesEnabled?: boolean;
    tiltGesturesEnabled?: boolean;
    rotateGesturesEnabled?: boolean;
    fastTapEnabled?: boolean;
    initialRegion?: InitialRegion;
    maxFps?: number;
    followUser?: boolean;
    logoPosition?: YandexLogoPosition;
    logoPadding?: YandexLogoPadding;
}
export declare class ClusteredYamap<T extends ClusteredMarkerData = ClusteredMarkerData> extends React.Component<ClusteredYaMapProps<T>> {
    static defaultProps: {
        showUserPosition: boolean;
        clusterColor: string;
        maxFps: number;
        markerSize: number;
    };
    map: React.RefObject<any>;
    static ALL_MASSTRANSIT_VEHICLES: Vehicles[];
    static init(apiKey: string): Promise<void>;
    static setLocale(locale: string): Promise<void>;
    static getLocale(): Promise<string>;
    static resetLocale(): Promise<void>;
    findRoutes(points: Point[], vehicles: Vehicles[], callback: (event: RoutesFoundEvent<DrivingInfo | MasstransitInfo>) => void): void;
    findMasstransitRoutes(points: Point[], callback: (event: RoutesFoundEvent<MasstransitInfo>) => void): void;
    findPedestrianRoutes(points: Point[], callback: (event: RoutesFoundEvent<MasstransitInfo>) => void): void;
    findDrivingRoutes(points: Point[], callback: (event: RoutesFoundEvent<DrivingInfo>) => void): void;
    fitAllMarkers(): void;
    setTrafficVisible(isVisible: boolean): void;
    fitMarkers(points: Point[]): void;
    setCenter(center: {
        lon: number;
        lat: number;
        zoom?: number;
    }, zoom?: number, azimuth?: number, tilt?: number, duration?: number, animation?: Animation): void;
    setZoom(zoom: number, duration?: number, animation?: Animation): void;
    getCameraPosition(callback: (position: CameraPosition) => void): void;
    getVisibleRegion(callback: (VisibleRegion: VisibleRegion) => void): void;
    getScreenPoints(points: Point[], callback: (screenPoint: ScreenPoint) => void): void;
    getWorldPoints(points: ScreenPoint[], callback: (point: Point) => void): void;
    private _findRoutes;
    private getCommand;
    private processRoute;
    private processCameraPosition;
    private processVisibleRegion;
    private processWorldToScreenPointsReceived;
    private processScreenToWorldPointsReceived;
    private resolveImageUri;
    private resolveMarkerIcons;
    private getProps;
    render(): React.JSX.Element;
}
