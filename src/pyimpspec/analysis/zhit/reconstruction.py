# pyimpspec is licensed under the GPLv3 or later (https://www.gnu.org/licenses/gpl-3.0.html).
# Copyright 2023 pyimpspec developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# The licenses of pyimpspec's dependencies and/or sources of portions of code are included in
# the LICENSES folder.

from multiprocessing import Pool
from typing import (
    Callable,
    Dict,
    List,
    Tuple,
)
from warnings import (
    catch_warnings,
    filterwarnings,
)
from numpy import (
    array,
    float64,
    isnan,
    pi,
)
from numpy.typing import NDArray
from pyimpspec.typing import Phases
from pyimpspec.progress import Progress


def _reconstruct(args) -> Tuple[NDArray[float64], str, str]:
    from scipy.integrate import (
        IntegrationWarning,
        quad,
    )

    ln_omega: NDArray[float64]
    interpolator: Callable
    derivator: Callable
    smoothing: str
    interpolation: str
    (ln_omega, interpolator, derivator, smoothing, interpolation) = args
    ln_modulus = []
    ln_w_s: float = ln_omega[0]
    i: int
    ln_w_0: float
    for i, ln_w_0 in enumerate(ln_omega):
        gamma = -pi / 6
        attempts: int = 10
        epsabs: float = 1e-9
        limit: int = 100
        with catch_warnings():
            filterwarnings("error", category=IntegrationWarning)
            while True:
                try:
                    integral = quad(
                        interpolator,
                        a=ln_w_s,
                        b=ln_w_0,
                        epsabs=epsabs,
                        limit=limit,
                    )[0]
                    break
                except IntegrationWarning as e:
                    attempts -= 1
                    if attempts <= 0:
                        break
                    msg: str = str(e)
                    if msg.startswith("The maximum number of subdivisions"):
                        limit += 100
                    elif msg.startswith("The occurrence of roundoff error"):
                        epsabs *= 10
                    else:
                        print(e)
                        break
        derivative = derivator(ln_w_0)
        if isnan(derivative):
            derivative = 0
        mod: float = 2 / pi * integral + gamma * derivative
        ln_modulus.append(mod)
    return (array(ln_modulus), smoothing, interpolation)


def _reconstruct_modulus_data(
    interpolation_options: Dict[str, Dict[str, Callable]],
    simulated_phase: Dict[str, Dict[str, Phases]],
    ln_omega: NDArray[float64],
    num_procs: int,
    prog: Progress,
) -> List[Tuple[NDArray[float64], Phases, str, str]]:
    prog.set_message("Reconstructing modulus data")
    reconstructions: List[Tuple[NDArray[float64], Phases, str, str]] = []
    args: List[Tuple[NDArray[float64], Callable, Callable, str, str]] = []
    interpolation: str
    for interpolation in interpolation_options:
        smoothing: str
        interpolator: Callable
        for smoothing, interpolator in interpolation_options[interpolation].items():
            args.append(
                (
                    ln_omega,
                    interpolator,
                    interpolator.derivative(1),
                    smoothing,
                    interpolation,
                )
            )
    ln_modulus: NDArray[float64]
    if len(args) > 1 and num_procs > 1:
        with Pool(num_procs) as pool:
            for (ln_modulus, smoothing, interpolation) in pool.imap_unordered(
                _reconstruct,
                args,
            ):
                reconstructions.append(
                    (
                        ln_modulus,
                        simulated_phase[interpolation][smoothing],
                        smoothing,
                        interpolation,
                    )
                )
                prog.increment()
    else:
        for (ln_modulus, smoothing, interpolation) in map(_reconstruct, args):
            reconstructions.append(
                (
                    ln_modulus,
                    simulated_phase[interpolation][smoothing],
                    smoothing,
                    interpolation,
                )
            )
            prog.increment()
    return reconstructions
