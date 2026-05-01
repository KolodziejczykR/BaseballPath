"""
Shared cross-domain constants for evaluation and matching.

Division benchmark data (mean + std) by position and division level,
used for PCI computation and metric comparisons.
"""

from typing import Dict


DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "exit_velo": {"mean": 95.4, "std": 5.97},
        "sixty_time": {"mean": 7.02, "std": 0.34},
        "inf_velo": {"mean": 84.66, "std": 5.29},
        "of_velo": {"mean": 86.94, "std": 5.57},
        "c_velo": {"mean": 79.02, "std": 3.9},
        "pop_time": {"mean": 1.99, "std": 0.1},
        "height": {"mean": 72.65, "std": 2.25},
        "weight": {"mean": 187.32, "std": 19.04},
    },
    "Non-P4 D1": {
        "exit_velo": {"mean": 93.4, "std": 5.58},
        "sixty_time": {"mean": 7.1, "std": 0.34},
        "inf_velo": {"mean": 82.94, "std": 5.01},
        "of_velo": {"mean": 85.53, "std": 4.94},
        "c_velo": {"mean": 77.54, "std": 3.87},
        "pop_time": {"mean": 2.0, "std": 0.1},
        "height": {"mean": 72.11, "std": 2.22},
        "weight": {"mean": 182.71, "std": 18.66},
    },
    "Mid-Major D1": {
        "exit_velo": {"mean": 93.72, "std": 5.65},
        "sixty_time": {"mean": 7.1, "std": 0.34},
        "inf_velo": {"mean": 83.16, "std": 5.02},
        "of_velo": {"mean": 86.03, "std": 4.72},
        "c_velo": {"mean": 77.78, "std": 3.94},
        "pop_time": {"mean": 2.0, "std": 0.1},
        "height": {"mean": 72.24, "std": 2.19},
        "weight": {"mean": 183.27, "std": 18.48},
    },
    "Low-Major D1": {
        "exit_velo": {"mean": 92.89, "std": 5.44},
        "sixty_time": {"mean": 7.11, "std": 0.35},
        "inf_velo": {"mean": 82.59, "std": 4.98},
        "of_velo": {"mean": 84.7, "std": 5.18},
        "c_velo": {"mean": 77.15, "std": 3.74},
        "pop_time": {"mean": 2.01, "std": 0.1},
        "height": {"mean": 71.88, "std": 2.26},
        "weight": {"mean": 181.72, "std": 18.93},
    },
    "D2": {
        "exit_velo": {"mean": 91.0, "std": 5.44},
        "sixty_time": {"mean": 7.25, "std": 0.35},
        "inf_velo": {"mean": 80.07, "std": 5.08},
        "of_velo": {"mean": 82.83, "std": 4.97},
        "c_velo": {"mean": 75.44, "std": 3.58},
        "pop_time": {"mean": 2.06, "std": 0.11},
        "height": {"mean": 71.52, "std": 2.3},
        "weight": {"mean": 179.35, "std": 19.98},
    },
    "D3": {
        "exit_velo": {"mean": 88.65, "std": 5.77},
        "sixty_time": {"mean": 7.35, "std": 0.39},
        "inf_velo": {"mean": 77.67, "std": 5.19},
        "of_velo": {"mean": 80.56, "std": 5.2},
        "c_velo": {"mean": 73.72, "std": 3.74},
        "pop_time": {"mean": 2.11, "std": 0.12},
        "height": {"mean": 71.12, "std": 2.33},
        "weight": {"mean": 175.38, "std": 20.56},
    },
}

PITCHER_DIVISION_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4": {
        "height": {"mean": 74.40, "std": 2.19},
        "weight": {"mean": 192.69, "std": 19.50},
        "FastballVelo Range": {"mean": 88.39, "std": 3.62},
        "FastballVelocity (max)": {"mean": 90.47, "std": 3.63},
        "FastballSpin Rate (avg)": {"mean": 2187.07, "std": 194.27},
        "Changeup Velo Range": {"mean": 79.49, "std": 4.27},
        "Changeup Spin Rate (avg)": {"mean": 1764.20, "std": 265.67},
        "Curveball Velo Range": {"mean": 74.22, "std": 4.14},
        "Curveball Spin Rate (avg)": {"mean": 2221.73, "std": 307.94},
        "Slider Velo Range": {"mean": 77.27, "std": 4.17},
        "Slider Spin Rate (avg)": {"mean": 2267.83, "std": 295.67},
    },
    "Non-P4 D1": {
        "height": {"mean": 73.69, "std": 2.24},
        "weight": {"mean": 187.89, "std": 19.33},
        "FastballVelo Range": {"mean": 85.92, "std": 3.40},
        "FastballVelocity (max)": {"mean": 87.88, "std": 3.39},
        "FastballSpin Rate (avg)": {"mean": 2137.07, "std": 177.43},
        "Changeup Velo Range": {"mean": 77.55, "std": 4.08},
        "Changeup Spin Rate (avg)": {"mean": 1710.87, "std": 262.72},
        "Curveball Velo Range": {"mean": 72.56, "std": 3.84},
        "Curveball Spin Rate (avg)": {"mean": 2149.25, "std": 281.01},
        "Slider Velo Range": {"mean": 75.09, "std": 4.00},
        "Slider Spin Rate (avg)": {"mean": 2191.69, "std": 277.93},
    },
    "Mid-Major D1": {
        "height": {"mean": 73.79, "std": 2.23},
        "weight": {"mean": 188.5, "std": 19.35},
        "FastballVelo Range": {"mean": 86.34, "std": 3.3},
        "FastballVelocity (max)": {"mean": 88.33, "std": 3.3},
        "FastballSpin Rate (avg)": {"mean": 2149.38, "std": 175.14},
        "Changeup Velo Range": {"mean": 77.88, "std": 4.02},
        "Changeup Spin Rate (avg)": {"mean": 1719.38, "std": 262.73},
        "Curveball Velo Range": {"mean": 72.89, "std": 3.77},
        "Curveball Spin Rate (avg)": {"mean": 2162.2, "std": 279.78},
        "Slider Velo Range": {"mean": 75.51, "std": 3.92},
        "Slider Spin Rate (avg)": {"mean": 2198.7, "std": 274.8},
    },
    "Low-Major D1": {
        "height": {"mean": 73.47, "std": 2.26},
        "weight": {"mean": 186.7, "std": 19.25},
        "FastballVelo Range": {"mean": 85.12, "std": 3.45},
        "FastballVelocity (max)": {"mean": 87.03, "std": 3.4},
        "FastballSpin Rate (avg)": {"mean": 2115.77, "std": 179.43},
        "Changeup Velo Range": {"mean": 76.92, "std": 4.13},
        "Changeup Spin Rate (avg)": {"mean": 1695.58, "std": 262.18},
        "Curveball Velo Range": {"mean": 71.94, "std": 3.88},
        "Curveball Spin Rate (avg)": {"mean": 2127.93, "std": 281.91},
        "Slider Velo Range": {"mean": 74.27, "std": 4.02},
        "Slider Spin Rate (avg)": {"mean": 2179.15, "std": 283.25},
    },
    "D2": {
        "height": {"mean": 73.10, "std": 2.33},
        "weight": {"mean": 183.80, "std": 20.86},
        "FastballVelo Range": {"mean": 82.72, "std": 3.70},
        "FastballVelocity (max)": {"mean": 84.53, "std": 3.75},
        "FastballSpin Rate (avg)": {"mean": 2048.72, "std": 188.77},
        "Changeup Velo Range": {"mean": 74.95, "std": 4.07},
        "Changeup Spin Rate (avg)": {"mean": 1650.76, "std": 257.34},
        "Curveball Velo Range": {"mean": 70.40, "std": 3.95},
        "Curveball Spin Rate (avg)": {"mean": 2061.99, "std": 278.57},
        "Slider Velo Range": {"mean": 72.58, "std": 3.89},
        "Slider Spin Rate (avg)": {"mean": 2112.39, "std": 260.86},
    },
    "D3": {
        "height": {"mean": 72.47, "std": 2.35},
        "weight": {"mean": 179.20, "std": 21.22},
        "FastballVelo Range": {"mean": 80.20, "std": 3.86},
        "FastballVelocity (max)": {"mean": 81.87, "std": 3.83},
        "FastballSpin Rate (avg)": {"mean": 1988.63, "std": 188.67},
        "Changeup Velo Range": {"mean": 72.99, "std": 4.00},
        "Changeup Spin Rate (avg)": {"mean": 1600.67, "std": 249.39},
        "Curveball Velo Range": {"mean": 68.44, "std": 4.04},
        "Curveball Spin Rate (avg)": {"mean": 1999.35, "std": 266.94},
        "Slider Velo Range": {"mean": 70.59, "std": 3.83},
        "Slider Spin Rate (avg)": {"mean": 2036.34, "std": 254.21},
    },
}


# Position-specific benchmarks

_OF_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4":         {"exit_velo": {"mean": 96.06, "std": 5.90}, "sixty_time": {"mean": 6.84, "std": 0.30}, "height": {"mean": 72.70, "std": 2.25}, "weight": {"mean": 186.34, "std": 17.79}, "of_velo": {"mean": 86.94, "std": 5.57}},
    "Non-P4 D1":  {"exit_velo": {"mean": 93.76, "std": 5.58}, "sixty_time": {"mean": 6.92, "std": 0.29}, "height": {"mean": 72.17, "std": 2.23}, "weight": {"mean": 180.94, "std": 16.62}, "of_velo": {"mean": 85.53, "std": 4.94}},
    "Mid-Major D1":{"exit_velo": {"mean": 94.00, "std": 5.77}, "sixty_time": {"mean": 6.93, "std": 0.30}, "height": {"mean": 72.32, "std": 2.18}, "weight": {"mean": 181.74, "std": 16.53}, "of_velo": {"mean": 86.03, "std": 4.72}},
    "Low-Major D1":{"exit_velo": {"mean": 93.36, "std": 5.23}, "sixty_time": {"mean": 6.90, "std": 0.28}, "height": {"mean": 71.90, "std": 2.30}, "weight": {"mean": 179.53, "std": 16.69}, "of_velo": {"mean": 84.70, "std": 5.18}},
    "D2":         {"exit_velo": {"mean": 91.43, "std": 5.35}, "sixty_time": {"mean": 7.06, "std": 0.31}, "height": {"mean": 71.55, "std": 2.26}, "weight": {"mean": 175.96, "std": 16.81}, "of_velo": {"mean": 82.83, "std": 4.97}},
    "D3":         {"exit_velo": {"mean": 89.24, "std": 5.51}, "sixty_time": {"mean": 7.15, "std": 0.32}, "height": {"mean": 71.13, "std": 2.23}, "weight": {"mean": 171.70, "std": 16.86}, "of_velo": {"mean": 80.56, "std": 5.20}},
}

_MIF_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4":         {"exit_velo": {"mean": 94.20, "std": 6.00}, "sixty_time": {"mean": 6.97, "std": 0.28}, "height": {"mean": 72.16, "std": 2.13}, "weight": {"mean": 178.67, "std": 15.37}, "inf_velo": {"mean": 85.24, "std": 5.10}},
    "Non-P4 D1":  {"exit_velo": {"mean": 91.91, "std": 5.30}, "sixty_time": {"mean": 7.05, "std": 0.29}, "height": {"mean": 71.49, "std": 2.10}, "weight": {"mean": 173.45, "std": 14.58}, "inf_velo": {"mean": 83.45, "std": 4.86}},
    "Mid-Major D1":{"exit_velo": {"mean": 92.30, "std": 5.33}, "sixty_time": {"mean": 7.04, "std": 0.27}, "height": {"mean": 71.61, "std": 2.11}, "weight": {"mean": 173.83, "std": 14.65}, "inf_velo": {"mean": 83.65, "std": 4.90}},
    "Low-Major D1":{"exit_velo": {"mean": 91.29, "std": 5.19}, "sixty_time": {"mean": 7.07, "std": 0.30}, "height": {"mean": 71.30, "std": 2.07}, "weight": {"mean": 172.80, "std": 14.45}, "inf_velo": {"mean": 83.14, "std": 4.77}},
    "D2":         {"exit_velo": {"mean": 89.37, "std": 5.41}, "sixty_time": {"mean": 7.16, "std": 0.30}, "height": {"mean": 70.74, "std": 2.15}, "weight": {"mean": 167.93, "std": 14.67}, "inf_velo": {"mean": 80.54, "std": 5.00}},
    "D3":         {"exit_velo": {"mean": 86.87, "std": 5.63}, "sixty_time": {"mean": 7.29, "std": 0.34}, "height": {"mean": 70.24, "std": 2.18}, "weight": {"mean": 163.99, "std": 15.37}, "inf_velo": {"mean": 78.20, "std": 5.16}},
}

_CIF_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4":         {"exit_velo": {"mean": 96.95, "std": 6.02}, "sixty_time": {"mean": 7.21, "std": 0.36}, "height": {"mean": 74.08, "std": 1.93}, "weight": {"mean": 203.22, "std": 19.48}, "inf_velo": {"mean": 83.34, "std": 5.48}},
    "Non-P4 D1":  {"exit_velo": {"mean": 95.44, "std": 5.63}, "sixty_time": {"mean": 7.30, "std": 0.33}, "height": {"mean": 73.50, "std": 2.05}, "weight": {"mean": 197.91, "std": 18.60}, "inf_velo": {"mean": 81.83, "std": 5.17}},
    "Mid-Major D1":{"exit_velo": {"mean": 95.59, "std": 5.82}, "sixty_time": {"mean": 7.28, "std": 0.33}, "height": {"mean": 73.64, "std": 2.00}, "weight": {"mean": 197.60, "std": 18.07}, "inf_velo": {"mean": 82.11, "std": 5.11}},
    "Low-Major D1":{"exit_velo": {"mean": 95.19, "std": 5.30}, "sixty_time": {"mean": 7.32, "std": 0.33}, "height": {"mean": 73.25, "std": 2.12}, "weight": {"mean": 198.46, "std": 19.52}, "inf_velo": {"mean": 81.38, "std": 5.23}},
    "D2":         {"exit_velo": {"mean": 92.63, "std": 5.30}, "sixty_time": {"mean": 7.42, "std": 0.34}, "height": {"mean": 72.71, "std": 2.25}, "weight": {"mean": 194.05, "std": 21.14}, "inf_velo": {"mean": 79.41, "std": 5.13}},
    "D3":         {"exit_velo": {"mean": 90.33, "std": 5.88}, "sixty_time": {"mean": 7.54, "std": 0.39}, "height": {"mean": 72.53, "std": 2.19}, "weight": {"mean": 191.90, "std": 21.89}, "inf_velo": {"mean": 76.91, "std": 5.13}},
}

_C_BENCHMARKS: Dict[str, Dict[str, Dict[str, float]]] = {
    "P4":         {"exit_velo": {"mean": 95.45, "std": 5.46}, "sixty_time": {"mean": 7.20, "std": 0.33}, "height": {"mean": 72.24, "std": 2.14}, "weight": {"mean": 192.15, "std": 16.35}, "c_velo": {"mean": 79.02, "std": 3.90}, "pop_time": {"mean": 1.99, "std": 0.10}},
    "Non-P4 D1":  {"exit_velo": {"mean": 93.75, "std": 5.37}, "sixty_time": {"mean": 7.28, "std": 0.33}, "height": {"mean": 71.96, "std": 2.04}, "weight": {"mean": 188.85, "std": 17.49}, "c_velo": {"mean": 77.54, "std": 3.87}, "pop_time": {"mean": 2.00, "std": 0.10}},
    "Mid-Major D1":{"exit_velo": {"mean": 94.14, "std": 5.28}, "sixty_time": {"mean": 7.27, "std": 0.33}, "height": {"mean": 72.09, "std": 1.95}, "weight": {"mean": 190.17, "std": 17.22}, "c_velo": {"mean": 77.78, "std": 3.94}, "pop_time": {"mean": 2.00, "std": 0.10}},
    "Low-Major D1":{"exit_velo": {"mean": 93.11, "std": 5.46}, "sixty_time": {"mean": 7.30, "std": 0.32}, "height": {"mean": 71.74, "std": 2.16}, "weight": {"mean": 186.66, "std": 17.72}, "c_velo": {"mean": 77.15, "std": 3.74}, "pop_time": {"mean": 2.01, "std": 0.10}},
    "D2":         {"exit_velo": {"mean": 91.11, "std": 5.18}, "sixty_time": {"mean": 7.40, "std": 0.34}, "height": {"mean": 71.37, "std": 2.06}, "weight": {"mean": 184.60, "std": 17.68}, "c_velo": {"mean": 75.44, "std": 3.58}, "pop_time": {"mean": 2.06, "std": 0.11}},
    "D3":         {"exit_velo": {"mean": 88.75, "std": 5.52}, "sixty_time": {"mean": 7.50, "std": 0.37}, "height": {"mean": 70.99, "std": 2.15}, "weight": {"mean": 179.91, "std": 18.12}, "c_velo": {"mean": 73.72, "std": 3.74}, "pop_time": {"mean": 2.11, "std": 0.12}},
}

_POSITION_TO_BENCHMARK: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
for _pos in ("OF", "CF", "RF", "LF", "OUTFIELDER"):
    _POSITION_TO_BENCHMARK[_pos] = _OF_BENCHMARKS
for _pos in ("SS", "2B", "MIF"):
    _POSITION_TO_BENCHMARK[_pos] = _MIF_BENCHMARKS
for _pos in ("3B", "1B"):
    _POSITION_TO_BENCHMARK[_pos] = _CIF_BENCHMARKS
for _pos in ("C", "CATCHER"):
    _POSITION_TO_BENCHMARK[_pos] = _C_BENCHMARKS


def get_position_benchmarks(position: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Return position-specific benchmarks, falling back to general DIVISION_BENCHMARKS."""
    pos = position.strip().upper() if position else ""
    return _POSITION_TO_BENCHMARK.get(pos, DIVISION_BENCHMARKS)


__all__ = ["DIVISION_BENCHMARKS", "PITCHER_DIVISION_BENCHMARKS", "get_position_benchmarks"]
