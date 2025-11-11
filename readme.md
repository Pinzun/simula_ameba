Estudio en profundidad simulación ameba

# Modelo de Expansión y Operación del Sistema Eléctrico

## 1\. Función Objetivo

$$
\begin{aligned}
\min \; Z &=
\sum_{y \in \mathcal{Y}}\sum_{t \in \mathcal{T}_y} \beta_y \Bigg[
\sum_{g \in \mathcal{G}} \Big(
c_g^{\text{var}}\, p_{g,y,t} +
c_g^{\text{su}}\, z^{\text{su}}_{g,y,t} +
c_g^{\text{sd}}\, z^{\text{sd}}_{g,y,t} +
c_g^{\text{vom}}\, u_{g,y,t}
\Big) \\
&\quad + \sum_{s \in \mathcal{S}} c_s^{\text{cyc}}\, e^{\text{cyc}}_{s,y,t}
+ \sum_{r \in \mathcal{R}} c_r^{\text{res}}\, r_{r,y,t}
\Bigg] \\
&\quad +
\sum_{k \in \mathcal{K}} \phi_{y_k} \Big(
C_k^{\text{fix}}\, b_k + C_k^{\text{cap}}\, \kappa_k
\Big) \\
&\quad +
\sum_{y \in \mathcal{Y}}\sum_{t \in \mathcal{T}_y} \beta_y
\sum_{n \in \mathcal{N}} \text{VOLL}_n \cdot \ell_{n,y,t}
\end{aligned}
$$

&nbsp;

## Desgloce

### Costos de generación

$$
\sum_{g \in \mathcal{G}} \Big(
c_g^{\text{var}}\, p_{g,y,t} +
c_g^{\text{su}}\, z^{\text{su}}_{g,y,t} +
c_g^{\text{sd}}\, z^{\text{sd}}_{g,y,t} +
c_g^{\text{vom}}\, u_{g,y,t}
\Big)
$$

Representa los costos de generación de cualquier unidad del sistema los que se componen de los costes variables de generación, costos por arrancar o apagar un generador, costos de operación y mantenimiento.

### Costos asociados a ESS

$$
 \sum_{s \in \mathcal{S}} c_s^{\text{cyc}}\, e^{\text{cyc}}_{s,y,t}
$$

La expresión anterior representa los costos totales asociados al ciclo de carga y descarga de la batería. El parámetro $c_s^{\text{cyc}}$ no se encuentra directamente en los archivos de entrada del modelo, pero es posible construir un proxy a partir de los datos disponibles.

$$
\text{E}_{\text{ciclo}} = \text{ess\_emax}\cdot \text{DoD}\\
\eta_{\text{rt}} = \text{ess\_effc}\cdot \text{ess\_effd}\\
\text{E}_{\text{vida}} = \text{E}_{\text{ciclo}}\cdot N_{\text{cy}}\cdot \text{lifetime}\cdot A\\
c^{\text{cyc}}_s \;[\$/\text{MWh}] \;\approx\; \frac{\text{gen\_inv\_cost}}{\text{E}_{\text{vida}}}
$$

&nbsp;$\text{ess\_emax}$ se debe definir como una constante un valor sugerido es 0.8

### Costos SSCC

$$
 \sum_{r \in \mathcal{R}} c_r^{\text{res}}\, r_{r,y,t}
$$

Representa el costo total de reserva ( SSCC). Estas reservas permiten cubrir variaciones inesperadas en la demanda o en la disponibilidad de los generadores de energía. Para modelar adecuadamente estos servicios, se define un conjunto de productos de reserva $\mathcal{R}$, donde cada tipo de reserva $r \in \mathcal{R}$ tiene un costo unitario asociado, denotado por $c_r^{\mathrm{res}}$.

Este parámetro representa el costo por megawatt (MW) de capacidad asignada a la reserva de tipo $r$ en un bloque $(y, t)$, y está expresado típicamente en unidades monetarias \[USD/MW\]. El término correspondiente en la función objetivo es:

$$
\sum_{r \in \mathcal{R}} c_r^{\mathrm{res}} \, r_{r,y,t}
$$

donde:

- $c_r^{\mathrm{res}}$ es el costo de proveer 1 MW de reserva del tipo $r$.
- $r_{r,y,t}$ es la cantidad de reserva del tipo $r$ asignada en el bloque $(y, t)$ [MW].

Cada tipo de reserva puede representar un producto con distintas características, por ejemplo:

- **Servicios de balance**
- **Servicios de control de tensión**

En el archivo de entrada (por ejemplo, `ThermalGenerator.csv` o `ESS.csv`), los valores de costos de reserva permiten modelar económicamente el rol de las unidades que participan en estos servicios.

_Al parecer la CNE no utiliza estos costos en la simulación del sistema_

### Costos de inversión

$$
\sum_{k \in \mathcal{K}} \phi_{y_k} \Big(
C_k^{\text{fix}}\, b_k + C_k^{\text{cap}}\, \kappa_k\Big)
$$

Representa los costos fijos de inversión más costos por unidad de capacidad instalada ambos anualizados

### Costos de falla

$$
\sum_{y \in \mathcal{Y}}\sum_{t \in \mathcal{T}_y} \beta_y
\sum_{n \in \mathcal{N}} \text{VOLL}_n \cdot \ell_{n,y,t}
$$

El término de costos de falla en la función objetivo representa el costo asociado a la demanda no servida (o energía que no se pudo suministrar) en cada nodo y bloque temporal:

- $\beta_y$: factor de descuento que ajusta el valor del costo al año base del estudio. Sirve para considerar el valor del dinero en el tiempo (por ejemplo: 1 MWh no servido hoy no vale lo mismo que en 10 años).
- $\text{VOLL}_n$: Valor de Energía No Suministrada en el nodo $n$ (Value of Lost Load). Es el costo de no abastecer 1 MWh en ese nodo.
- $\ell_{n,y,t}$: energía no servida (en MWh) en el nodo $n$ durante el año $y$ y bloque temporal $t$.
  &nbsp;

---

## 2\. Restricciones

### Balance de Potencia por Nodo

$$
\sum_{g \in \mathcal{G}_n} p_{g,y,t}

- D_{n,y,t}

+ \sum_{s \in \mathcal{S}_n} \left( p^{\text{dis}}_{s,y,t} - p^{\text{ch}}_{s,y,t} \right)
+ \ell_{n,y,t}
+ \sum_{l \in \mathcal{L}} A_{l,n} \, f_{l,y,t}
= 0


$$

El balance de potencia asegura que, en cada nodo de la red y en cada bloque temporal, la energía inyectada al sistema sea igual a la demandada, considerando generación, almacenamiento, flujo entre nodos y eventual corte de carga. A continuación se describe cada parte de la expresión:

- $\sum_{g \in \mathcal{G}n} p{g,y,t}$. Potencia generada en el nodo $n$ por cada unidad $g$ conectada al nodo.
- $-D_{n,y,t}$ Potencia demandada en el nodo $n$ en el intervalo $(y,t)$. Se resta porque es consumo.
- $\sum_{s \in \mathcal{S}n} \left( p^{\mathrm{dis}}{s,y,t} - p^{\mathrm{ch}}_{s,y,t} \right)$. Diferencia neta entre energía descargada y cargada por sistemas de almacenamiento en el nodo $n$: - $p^{\mathrm{dis}}_{s,y,t}$. es la descarga (positivo). - $p^{\mathrm{ch}}_{s,y,t}$. es la carga (negativo).
- $\ell_{n,y,t}$. Energía no servida en el nodo $n$, modelada como variable de corte de carga.
- $\sum_{l \in \mathcal{L}} A_{l,n} , f_{l,y,t}$. Flujo neto de potencia hacia o desde el nodo $n$, considerando la matriz de incidencia $A$:
- Si $A_{l,n} = 1$ el flujo entra al nodo.
- Si $A_{l,n} = -1$ el flujo sale del nodo.

Este balance debe cumplirse para todo nodo $n$, toda etapa $y$ y todo bloque temporal $t$, asegurando que el flujo eléctrico respete las leyes físicas de conservación de energía.

### Dinámica del Estado de Carga del ESS

$$
E_{s,y,t+1}
= E_{s,y,t}

+ \eta^{\text{ch}}_s \, p^{\text{ch}}_{s,y,t} \, \Delta t

- \frac{1}{\eta^{\text{dis}}_s} \, p^{\text{dis}}_{s,y,t} \, \Delta t


$$

La expresión modela la evolución del nivel de carga $E$ del sistema de almacenamiento $s$ entre dos bloques temporales consecutivos $(y,t)$ y $(y,t+1)$, considerando la energía cargada y descargada en el período.

- $E_{s,y,t}$ y $E_{s,y,t+1}$. Estado de carga (State of Charge, SoC) del almacenamiento $s$ al inicio y final del bloque temporal $(y,t)$, respectivamente. Se mide en unidades de energía (por ejemplo, MWh).
- $\eta^{\mathrm{ch}}_s$. Eficiencia de carga del sistema de almacenamiento $s$. Es un valor entre 0 y 1.
- $p^{\mathrm{ch}}_{s,y,t}$. Potencia de carga hacia el almacenamiento $s$ en el bloque $(y,t)$ (MW).
- $\eta^{\mathrm{dis}}_s$. Eficiencia de descarga del sistema. La energía descargada se penaliza dividiendo por este factor (también entre 0 y 1).
- $p^{\mathrm{dis}}_{s,y,t}$. Potencia de descarga del almacenamiento $s$ en el bloque $(y,t)$ (MW).
- $\Delta t$. Duración del bloque temporal (horas).

Esta ecuación asegura que el nivel de carga del almacenamiento evolucione respetando la eficiencia y la potencia de carga/descarga, y que no se cree ni destruya energía de forma arbitraria en el sistema.

&nbsp;

### Dinámica de Volumen de Embalses

$$
S_{r,y,t+1}
= S_{r,y,t}
+ I_{r,y,t}
- R_{r,y,t}
- Q^{\mathrm{spill}}_{r,y,t}
- Q^{\mathrm{irr}}_{r,y,t}


$$

La expresión anterior modela la evolución del volumen almacenado en el embalse $r$ entre dos bloques temporales consecutivos $(y,t)$ y $(y,t+1)$, considerando los aportes naturales, la generación hidroeléctrica, el vertimiento y el riego.
• $S_{r,y,t}$ y $S_{r,y,t+1}$. Volumen de agua almacenado en el embalse $r$ al inicio y final del bloque temporal $(y,t)$, respectivamente (en Hm³).
• $I_{r,y,t}$. Aporte natural de agua (inflow) al embalse $r$ durante el bloque $(y,t)$ (Hm³).
• $R_{r,y,t}$. Volumen de agua turbinada o liberada desde el embalse $r$ para generación hidroeléctrica en el bloque $(y,t)$ (Hm³).
• $Q^{\mathrm{spill}}_{r,y,t}$. Volumen de agua vertido (spill) al río o vertedero en el bloque $(y,t)$ (Hm³).
• $Q^{\mathrm{irr}}_{r,y,t}$. Volumen de agua destinado a usos de riego durante el bloque $(y,t)$ (Hm³), el cual se debe satisfacer de forma obligatoria en cada bloque temporal (riego obligatorio ).

Dada la obligatoriedad, se impone:

$$
Q^{\mathrm{irr}}_{r,y,t}
=
D^{\mathrm{irr}}_{r,y,t}
$$

donde $D^{\mathrm{irr}}_{r,y,t}$ representa la demanda de riego requerida desde el embalse $r$ en el bloque $(y,t)$.

Esta versión de la ecuación de balance asegura la conservación de masa en el embalse y cumple de forma estricta con la obligación de entrega de agua para riego, sin considerar pérdidas adicionales ni límites de caudal en canales de distribución.

### Cotas

$$
0 \leq p_{g,y,t} \leq u_{g,y,t} \cdot P^{\max}_g


\ell_{n,y,t} \ge 0
\quad,\quad
Q^{\text{spill}}_{r,y,t} \ge 0


$$

A continuación la explicación de cada una de la expresiones:

$0 \leq p_{g,y,t} \leq u_{g,y,t} \cdot P^{\max}_g$

Esta restricción asegura que la potencia generada por cada unidad térmica o hidroeléctrica $g$ en el bloque $(y,t)$:

- No sea negativa.
- No exceda su potencia máxima $P^{\max}_g$.
- Quede condicionada por su estado de operación $u_{g,y,t}$ (0=apagado, 1=encendido).
  Si la unidad está apagada ($u_{g,y,t} = 0$), entonces $p_{g,y,t} = 0$; si está operativa ($u_{g,y,t}=1$), puede generar hasta su capacidad nominal $P^{\max}_g$.

$\ell_{n,y,t} \ge 0
\quad,\quad
Q^{\text{spill}}_{r,y,t} \ge 0$

Estas restricciones imponen que:

- $\ell_{n,y,t}$, la demanda no servida (corte de carga) en el nodo $n$ durante el bloque $(y,t)$, nunca puede ser negativa.
- $Q^{\mathrm{spill}}_{r,y,t}$, el vertimiento de agua desde el embalse $r$ en el bloque $(y,t)$, tampoco puede ser negativo.

Ambas variables representan fenómenos indeseados (fallas de suministro y pérdidas de recurso hídrico respectivamente), por lo que no se permite que “compensen” o reduzcan otras magnitudes en el balance energético o hídrico.

---

## 3\. Variables

- $u_{g,y,t} \in \{0, 1\}$: estado ON/OFF de la unidad generadora $g$ en $(y,t)$
- $z^{\mathrm{su}}_{g,y,t} \in \{0, 1\}$: vale 1 si el generador $g$ arranca en $(y,t)$
- $z^{\mathrm{sd}}_{g,y,t} \in \{0, 1\}$: vale 1 si el generador $g$ se apaga en $(y,t)$
- $b_k \in \{0, 1\}$: vale 1 si se construye el candidato de inversión $k$
- $p_{g,y,t} \ge 0$: potencia generada por la unidad $g$ en $(y,t)$ \[MW\]
- $e^{\mathrm{cyc}}_{s,y,t} \ge 0$: energía cíclica del sistema de almacenamiento $s$ en $(y,t)$ \[MWh\]
- $r_{r,y,t} \ge 0$: reserva provista del tipo $r$ en $(y,t)$ \[MW\]
- $\kappa_k \ge 0$: capacidad instalada asociada al candidato $k$ \[MW o MWh\]
- $\ell_{n,y,t} \ge 0$: carga no servida en el nodo $n$ en $(y,t)$ \[MWh\]

---

## 4\. Parámetros

- $\beta_{y}$: factor de descuento asociado a la etapa $y$
- $c_{g}^{\mathrm{var}}$: costo variable de operación del generador $g$ \[USD/MWh\]
- $c_{g}^{\mathrm{su}}$: costo de arranque de generador $g$ \[USD/arranque\]
- $c_{g}^{\mathrm{sd}}$: costo de apagado de generador $g$ \[USD/apagado\]
- $c_{g}^{\mathrm{vom}}$: costo variable de O&M del generador $g$ \[USD/MWh\]
- $c_{s}^{\mathrm{cyc}}$: costo cíclico del almacenamiento $s$ \[USD/MWh\]
- $c_{r}^{\mathrm{res}}$: costo asociado a reserva del tipo $r$ \[USD/MW\]
- $C_{k}^{\mathrm{fix}}$: costo fijo de inversión del candidato $k$
- $C_{k}^{\mathrm{cap}}$: costo por unidad de capacidad instalada del candidato $k$
- $\phi_{y_k}$: factor financiero (NPV/anualidad) para inversión en el activo $k$
- $\mathrm{VOLL}_n$: valor de energía no servida en el nodo $n$ \[USD/MWh\]

---

&nbsp;

&nbsp;

&nbsp;

&nbsp;

# Anexo: Archivos de entrada del modelo

## `blocks.csv`

Este archivo define la estructura temporal del modelo eléctrico a través de etapas (`stage`) y bloques horario-temporales (`block`), junto con su marca de tiempo asociada (`time`).

| Columna | Descripción                                                                                                                         | Unidad                            |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `stage` | Índice de etapa o período del modelo. Usualmente representa un año, mes o subconjunto de tiempo superior que agrupa varios bloques. | Entero (1, 2, 3, …)               |
| `block` | Índice del bloque horario dentro de una misma etapa. Define la división del tiempo en subperíodos continuos dentro del `stage`.     | Entero (1, 2, 3, …)               |
| `time`  | Marca de tiempo correspondiente al inicio del bloque. Permite asociar este bloque a un instante de tiempo real.                     | Fecha y hora (`YYYY-MM-DD-HH:MM`) |

## `demand.csv`

| Columna               | Descripción                                                                          | Unidad                            |
| --------------------- | ------------------------------------------------------------------------------------ | --------------------------------- |
| time                  | Marca de tiempo en la que se registra la demanda eléctrica para todos los nodos.     | Fecha y hora (`YYYY-MM-DD-HH:MM`) |
| scenario              | Nombre o identificador del escenario de demanda (por ejemplo: `BAU`, `LOW`, `HIGH`). | Texto                             |
| L_NuevaCharrua500     | Demanda eléctrica en el barra `NuevaCharrua500`.                                     | MW                                |
| L_Cumbre500           | Demanda eléctrica en el barra `Cumbre500`.                                           | MW                                |
| L_Pichirropulli500    | Demanda eléctrica en el barra `Pichirropulli500`.                                    | MW                                |
| L_Polpaico500         | Demanda eléctrica en el barra `Polpaico500`.                                         | MW                                |
| L_Ancud500            | Demanda eléctrica en el barra `Ancud500`.                                            | MW                                |
| L_AltoJahuel500       | Demanda eléctrica en el barra `AltoJahuel500`.                                       | MW                                |
| L_NuevaCardones500    | Demanda eléctrica en el barra `NuevaCardones500`.                                    | MW                                |
| L_Ancoa500            | Demanda eléctrica en el barra `Ancoa500`.                                            | MW                                |
| L_RioMalleco500       | Demanda eléctrica en el barra `RioMalleco500`.                                       | MW                                |
| L_NuevaPandeAzucar500 | Demanda eléctrica en el barra `NuevaPandeAzucar500`.                                 | MW                                |
| L_NuevaMaitencillo500 | Demanda eléctrica en el barra `NuevaMaitencillo500`.                                 | MW                                |
| L_NuevaPuertoMontt500 | Demanda eléctrica en el barra `NuevaPuertoMontt500`.                                 | MW                                |
| L_Parinas500          | Demanda eléctrica en el barra `Parinas500`.                                          | MW                                |
| L_NuevaZaldivar220    | Demanda eléctrica en el barra `NuevaZaldivar220`.                                    | MW                                |
| L_Kimal500            | Demanda eléctrica en el barra `Kimal500`.                                            | MW                                |
| L_LosChangos500       | Demanda eléctrica en el barra `LosChangos500`.                                       | MW                                |
| L_Lagunas220          | Demanda eléctrica en el barra `Lagunas220`.                                          | MW                                |
| L_Kimal220            | Demanda eléctrica en el barra `Kimal220`.                                            | MW                                |
| L_LosChangos220       | Demanda eléctrica en el barra `LosChangos220`.                                       | MW                                |
| L_Parinacota220       | Demanda eléctrica en el barra `Parinacota220`.                                       | MW                                |
| L_NuevaPozoAlmonte220 | Demanda eléctrica en el barra `NuevaPozoAlmonte220`.                                 | MW                                |
| L_Quillota500         | Demanda eléctrica en el barra `Quillota500`.                                         | MW                                |
| L_Rapel500            | Demanda eléctrica en el barra `Rapel500`.                                            | MW                                |
| L_Concepcion500       | Demanda eléctrica en el barra `Concepcion500`.                                       | MW                                |
| L_Mulchen500          | Demanda eléctrica en el barra `Mulchen500`.                                          | MW                                |
| L_Candelaria500       | Demanda eléctrica en el barra `Candelaria500`.                                       | MW                                |

## `factor.csv`

| Columna                  | Descripción                                                               | Unidad                            |
| ------------------------ | ------------------------------------------------------------------------- | --------------------------------- |
| time`                    | Instante de tiempo al que corresponde el factor de proyección de demanda. | Fecha y hora (`YYYY-MM-DD-HH:MM`) |
| Proj_NuevaCharrua500     | Factor de proyección asociado al nodo `NuevaCharrua500`.                  | Adimensional                      |
| Proj_Cumbre500           | Factor de proyección asociado al nodo `Cumbre500`.                        | Adimensional                      |
| Proj_Pichirropulli500    | Factor de proyección asociado al nodo `Pichirropulli500`.                 | Adimensional                      |
| Proj_Polpaico500         | Factor de proyección asociado al nodo `Polpaico500`.                      | Adimensional                      |
| Proj_Ancud500            | Factor de proyección asociado al nodo `Ancud500`.                         | Adimensional                      |
| Proj_AltoJahuel500       | Factor de proyección asociado al nodo `AltoJahuel500`.                    | Adimensional                      |
| Proj_NuevaCardones500    | Factor de proyección asociado al nodo `NuevaCardones500`.                 | Adimensional                      |
| Proj_Ancoa500            | Factor de proyección asociado al nodo `Ancoa500`.                         | Adimensional                      |
| Proj_RioMalleco500       | Factor de proyección asociado al nodo `RioMalleco500`.                    | Adimensional                      |
| Proj_NuevaPandeAzucar500 | Factor de proyección asociado al nodo `NuevaPandeAzucar500`.              | Adimensional                      |
| Proj_NuevaMaitencillo500 | Factor de proyección asociado al nodo `NuevaMaitencillo500`.              | Adimensional                      |
| Proj_NuevaPuertoMontt500 | Factor de proyección asociado al nodo `NuevaPuertoMontt500`.              | Adimensional                      |
| Proj_Parinas500          | Factor de proyección asociado al nodo `Parinas500`.                       | Adimensional                      |
| Proj_NuevaZaldivar220    | Factor de proyección asociado al nodo `NuevaZaldivar220`.                 | Adimensional                      |
| Proj_Kimal500            | Factor de proyección asociado al nodo `Kimal500`.                         | Adimensional                      |
| Proj_LosChangos500       | Factor de proyección asociado al nodo `LosChangos500`.                    | Adimensional                      |
| Proj_Lagunas220          | Factor de proyección asociado al nodo `Lagunas220`.                       | Adimensional                      |
| Proj_Kimal220            | Factor de proyección asociado al nodo `Kimal220`.                         | Adimensional                      |
| Proj_LosChangos220       | Factor de proyección asociado al nodo `LosChangos220`.                    | Adimensional                      |
| Proj_Parinacota220       | Factor de proyección asociado al nodo `Parinacota220`.                    | Adimensional                      |
| Proj_NuevaPozoAlmonte220 | Factor de proyección asociado al nodo `NuevaPozoAlmonte220`.              | Adimensional                      |
| Proj_Quillota500         | Factor de proyección asociado al nodo `Quillota500`.                      | Adimensional                      |
| Proj_Rapel500            | Factor de proyección asociado al nodo `Rapel500`.                         | Adimensional                      |
| Proj_Concepcion500       | Factor de proyección asociado al nodo `Concepcion500`.                    | Adimensional                      |
| Proj_Mulchen500          | Factor de proyección asociado al nodo `Mulchen500`.                       | Adimensional                      |
| Proj_Candelaria500       | Factor de proyección asociado al nodo `Candelaria500`.                    | Adimensional                      |

## `fuel_price`

| **Columna**                    | **Descripción**                              | **Unidad**     |
| ------------------------------ | -------------------------------------------- | -------------- |
| time                           | Marca temporal del valor reportado           | Año/Mes o Hora |
| scenario                       | Nombre del escenario o caso modelado         | Texto          |
| Fuel_ALMENDRADO_Diesel         | Precio del diésel para la planta Almendrado  | USD/MMBtu      |
| Fuel_ANCALI_1_Biogas           | Precio del biogás para la planta Ancali 1    | USD/MMBtu      |
| Fuel_ANDES_U1_DIE_Diesel       | Precio del diésel para la unidad 1 en Andes  | USD/MMBtu      |
| Fuel_ANDES_U2_DIE_Diesel       | Precio del diésel para la unidad 2 en Andes  | USD/MMBtu      |
| Fuel_ARAUCO_Biomasa            | Precio de biomasa para la unidad Arauco      | USD/MMBtu      |
| Fuel_HBS_GN                    | Precio de gas natural para HBS               | USD/MMBtu      |
| Fuel_NEHUENCO_1-TG+TV_GNL_E_GN | Precio de GNL para Nehuenco (TG+TV unidad 1) | USD/MMBtu      |
| ...                            | ...                                          | ...            |

_Muestra un resumen del dataframe_

## `gen_inv_cost`

| Column Name     | Description                                                  | Unit   |
| --------------- | ------------------------------------------------------------ | ------ |
| time            | Year or time period associated with the investment cost data | Year   |
| scenario        | Simulation or planning scenario (e.g., BAU, NetZero)         | Text   |
| Biomasa_Ancoa   | Cost of investment for biomass plant in Ancoa                | USD/kW |
| Biomasa_Cautin  | Cost of investment for biomass plant in Cautin               | USD/kW |
| Biomasa_Charrua | Cost of investment for biomass plant in Charrua              | USD/kW |
| ...             | ...                                                          | ...    |

_Muestra un resumen del dataframe_

## `inflows_qm3`

| Columna         | Descripción                                              | Unidad         |
| --------------- | -------------------------------------------------------- | -------------- |
| time            | Marca temporal del registro (día/hora)                   | \-             |
| scenario        | Escenario hidrológico (puede ser un ID o valor numérico) | \-             |
| Afl_Ancoa       | Caudal en el río Ancoa                                   | Hm³ por bloque |
| Afl_Rio_Melado  | Aporte del río Melado                                    | Hm³ por bloque |
| Afl_Hid_Rapel02 | Afluencia a la unidad hidroeléctrica Rapel 02            | Hm³ por bloque |
| Afl_PMGDMulchen | Caudal asociado a un PMGD en Mulchén                     | Hm³ por bloque |

## `Branch`

| Columna                    | Descripción                                            | Unidad                 |
| -------------------------- | ------------------------------------------------------ | ---------------------- |
| name                       | Nombre de la línea o ramal                             | \-                     |
| start_time                 | Fecha/hora de inicio de validez del registro           | ISO 8601 (YYYY-MM-DD)  |
| end_time                   | Fecha/hora de término de validez                       | ISO 8601 (YYYY-MM-DD)  |
| report                     | Bandera para determinar si se reporta en salidas       | Booleano (True/False)  |
| connected                  | Indica si la línea está activa/conectada al sistema    | Booleano (True/False)  |
| coordinates                | Coordenadas geográficas asociadas (si aplica)          | Lat/Lon (WKT o JSON)   |
| busbari                    | Barra de origen (sending end)                          | \-                     |
| busbarf                    | Barra de destino (receiving end)                       | \-                     |
| max_flow                   | Límite térmico/normativo de flujo en dirección forward | MW                     |
| max_flow_reverse           | Límite de flujo en dirección reverse                   | MW                     |
| r                          | Resistencia serie de la línea                          | Ohm (Ω) o p.u.         |
| x                          | Reactancia serie de la línea                           | Ohm (Ω) o p.u.         |
| branch_associated_ess      | ESS asociado si corresponde                            | \-                     |
| branch_ovf_ab              | Costo de sobrecarga AB (de barra i a f)                | USD/MWh (penalización) |
| branch_ovf_ba              | Costo de sobrecarga BA (de barra f a i)                | USD/MWh (penalización) |
| dc                         | Indicador si es modelada como línea DC                 | Booleano               |
| losses                     | Porcentaje o modelo de pérdidas                        | % o modelo definido    |
| binary_loss_model          | Uso de modelo binario para pérdidas                    | Booleano               |
| candidate                  | Indica si es activo candidato de inversión             | Booleano               |
| branch_recourse            | Determina si admite re-optimización (recourse)         | Booleano               |
| branch_recourse_start_time | Periodo desde el cual el recourse aplica               | ISO 8601 (YYYY-MM-DD)  |
| dimensioned                | Indica si tiene dimensión física definida              | Booleano               |
| branch_inv_cost            | Costo total de inversión para construir la línea       | USD                    |
| initial_investment         | Inversión inicial o CAPEX                              | USD                    |
| lifetime                   | Vida útil del activo                                   | Años                   |
| voltage                    | Nivel de tensión de la línea                           | kV                     |
| owner                      | Entidad propietaria                                    | \-                     |

## `Busbar`

| Columna     | Descripción                                                | Unidad    |
| ----------- | ---------------------------------------------------------- | --------- |
| name        | Nombre único que identifica la barra (busbar)              | \-        |
| start_time  | Fecha/hora de inicio de vigencia del registro              | Timestamp |
| end_time    | Fecha/hora de término de vigencia del registro             | Timestamp |
| report      | Indica si la barra debe incluirse en reportes (True/False) | \-        |
| coordinates | Coordenadas geográficas o espaciales de la barra           | lat, lon  |
| prices      | Precio marginal de energía asociado a la barra (opcional)  | USD/MWh   |
| voltage     | Nivel de tensión nominal de la barra                       | kV        |
| owner       | Nombre del dueño o entidad propietaria de la barra         | \-        |

## `ControlArea`

| Columna              | Descripción                                                       | Unidad    |
| -------------------- | ----------------------------------------------------------------- | --------- |
| name                 | Nombre del área de control                                        | \-        |
| start_time           | Fecha/hora de inicio de vigencia del registro                     | Timestamp |
| end_time             | Fecha/hora de término de vigencia del registro                    | Timestamp |
| report               | Indica si el área debe incluirse en reportes (True/False)         | \-        |
| rpreq_up             | Requerimiento de reserva primaria hacia arriba                    | MW        |
| rpreq_down           | Requerimiento de reserva primaria hacia abajo                     | MW        |
| rsreq_up             | Requerimiento de reserva secundaria hacia arriba                  | MW        |
| rsreq_down           | Requerimiento de reserva secundaria hacia abajo                   | MW        |
| rtreq_up             | Requerimiento de reserva terciaria hacia arriba                   | MW        |
| rtreq_down           | Requerimiento de reserva terciaria hacia abajo                    | MW        |
| rtreq                | Requerimiento total de reserva terciaria                          | MW        |
| max_pv_penetration   | Porcentaje máximo de penetración permitido para generación solar  | %         |
| max_wind_penetration | Porcentaje máximo de penetración permitido para generación eólica | %         |
| inertia_req          | Requerimiento mínimo de inercia para el área                      | MW·s      |

## `Dam`

| Columna                     | Descripción                                                                      | Unidad     |
| --------------------------- | -------------------------------------------------------------------------------- | ---------- |
| name                        | Nombre del embalse                                                               | \-         |
| start_time                  | Fecha/hora de inicio de vigencia del registro                                    | Timestamp  |
| end_time                    | Fecha/hora de término de vigencia del registro                                   | Timestamp  |
| report                      | Indica si el embalse debe incluirse en reportes (True/False)                     | \-         |
| vmax                        | Volumen máximo permitido en el embalse                                           | Hm³        |
| vmin                        | Volumen mínimo permitido en el embalse                                           | Hm³        |
| vini                        | Volumen inicial del embalse al inicio de la simulación                           | Hm³        |
| vend                        | Volumen objetivo al final del horizonte de simulación                            | Hm³        |
| scale                       | Factor de escala para ajustar los volúmenes o caudales asociados al embalse      | \-         |
| non_physical_inflow         | Aporte no físico artificial al embalse (por ejemplo, para rellenos operativos)   | Hm³        |
| non_physical_inflow_penalty | Penalidad asociada al uso de aportes no físicos                                  | USD/Hm³    |
| filt_avg                    | Indicador de si se filtra la serie de inflows usando promedio móvil (True/False) | \-         |
| use_fcf                     | Indica si se considera curva de consumo objetivo (firm capacity factor)          | True/False |
| cond_ovf                    | Condición para activar vertimiento obligatorio                                   | \-         |
| vol_ovf                     | Volumen sobre el cual se activa penalidad por exceso                             | Hm³        |
| val_ovf                     | Penalidad asociada a exceder el volumen permitido                                | USD/Hm³    |
| filt_poly                   | Parámetro para suavizar aportes a través de ajuste polinómico                    | \-         |
| candidate                   | Indica si el embalse es una opción de inversión (True/False)                     | \-         |
| owner                       | Propietario del embalse                                                          | \-         |

## `ESS`

| Columna                   | Descripción                                                                  | Unidad     |
| ------------------------- | ---------------------------------------------------------------------------- | ---------- |
| name                      | Nombre del sistema de almacenamiento (ESS)                                   | \-         |
| start_time                | Inicio de vigencia del registro                                              | Timestamp  |
| end_time                  | Fin de vigencia del registro                                                 | Timestamp  |
| report                    | Indica si el ESS se incluye en los reportes (True/False)                     | \-         |
| coordinates               | Coordenadas geográficas del ESS                                              | lat,lon    |
| busbar                    | Barra de conexión eléctrica                                                  | \-         |
| connected                 | Indica si el ESS está conectado a la red (True/False)                        | \-         |
| control_areas             | Áreas de control asociadas al ESS                                            | \-         |
| ess_associated_generators | Generadores asociados al ESS (si aplica, para cargado/descargado coordinado) | \-         |
| pmax                      | Potencia máxima de descarga                                                  | MW         |
| ess_pmaxc                 | Potencia máxima de carga                                                     | MW         |
| pmin                      | Potencia mínima de descarga                                                  | MW         |
| ess_pminc                 | Potencia mínima de carga                                                     | MW         |
| rpmax_up                  | Capacidad máxima de reserva primaria hacia arriba                            | MW         |
| rpmax_down                | Capacidad máxima de reserva primaria hacia abajo                             | MW         |
| rsmax_up                  | Capacidad máxima de reserva secundaria hacia arriba                          | MW         |
| rsmax_down                | Capacidad máxima de reserva secundaria hacia abajo                           | MW         |
| rtmax_up                  | Capacidad máxima de reserva terciaria hacia arriba                           | MW         |
| rtmax_down                | Capacidad máxima de reserva terciaria hacia abajo                            | MW         |
| pcost_rp_up               | Costo por MW de oferta de reserva primaria hacia arriba                      | USD/MW     |
| pcost_rs_up               | Costo por MW de reserva secundaria hacia arriba                              | USD/MW     |
| pcost_rt_up               | Costo por MW de reserva terciaria hacia arriba                               | USD/MW     |
| pcost_rp_down             | Costo por MW de reserva primaria hacia abajo                                 | USD/MW     |
| pcost_rs_down             | Costo por MW de reserva secundaria hacia abajo                               | USD/MW     |
| pcost_rt_down             | Costo por MW de reserva terciaria hacia abajo                                | USD/MW     |
| vomc_avg                  | Costo operativo variable medio (VOM)                                         | USD/MWh    |
| auxserv                   | Consumo de servicios auxiliares del ESS                                      | %          |
| flex                      | Indicador de flexibilidad operativa                                          | \-         |
| uc_linear                 | Indica si el ESS usa modelo unit commitment linealizado (True/False)         | \-         |
| ess_type                  | Tipo de ESS (por ejemplo, Batería, Hidrógeno, etc.)                          | \-         |
| ess_eini                  | Energía inicial almacenada en el ESS                                         | MWh        |
| ess_emax                  | Energía máxima almacenable                                                   | MWh        |
| ess_emin                  | Energía mínima operativa                                                     | MWh        |
| ess_effn                  | Eficiencia round-trip total                                                  | %          |
| ess_intrastage_balance    | Bandera para balance intrablock                                              | True/False |
| ess_effc                  | Eficiencia de carga del ESS                                                  | %          |
| ess_effd                  | Eficiencia de descarga del ESS                                               | %          |
| is_ncre                   | Indica si es una unidad de energía renovable no convencional (True/False)    | \-         |
| forced_commit             | Indica si el ESS está obligado a operar (commit)                             | True/False |
| unavailability            | Tasa de indisponibilidad del sistema                                         | %          |
| candidate                 | Indica si el ESS es una opción de inversión                                  | True/False |
| gen_recourse              | Generación sujeta a recourse en escenarios                                   | True/False |
| gen_recourse_start_time   | Tiempo de inicio del recourse                                                | Timestamp  |
| dimensioned               | Indica si el ESS tiene dimensiones predeterminadas                           | True/False |
| gen_inv_cost              | Costo de inversión asociado                                                  | USD        |
| initial_investment        | Costo inicial de inversión del ESS                                           | USD        |
| recog_pot                 | Potencia recuperable                                                         | MW         |
| forced_outage_rate        | Tasa de falla forzada                                                        | %          |
| fom_cost                  | Costo fijo de O&M anual                                                      | USD/MW/año |
| lifetime                  | Vida útil esperada del equipo                                                | Años       |
| inertia                   | Contribución a inercia del sistema                                           | MW·s       |
| voltage                   | Nivel de voltaje de conexión                                                 | kV         |
| owner                     | Propietario del ESS                                                          | \-         |

## `Fuel`

| Columna               | Descripción                                                                | Unidad       |
| --------------------- | -------------------------------------------------------------------------- | ------------ |
| name                  | Nombre del combustible o fuente de energía                                 | \-           |
| start_time            | Fecha de inicio de vigencia del registro                                   | Timestamp    |
| end_time              | Fecha de término de vigencia del registro                                  | Timestamp    |
| report                | Indica si el combustible se incluye en los reportes (True/False)           | \-           |
| fuel_type             | Tipo de combustible (por ejemplo, Diesel, Gas Natural, Biomasa, etc.)      | \-           |
| fuel_price            | Precio del combustible                                                     | USD/MMBtu    |
| availability          | Disponibilidad del combustible (normalmente en fracción o %)               | % o fracción |
| consider_availability | Indica si la disponibilidad debe ser considerada en el modelo (True/False) | \-           |

## `HydroConnection `

| Columna        | Descripción                                                           | Unidad          |
| -------------- | --------------------------------------------------------------------- | --------------- |
| name           | Nombre de la conexión hidráulica                                      | \-              |
| start_time     | Fecha de inicio de vigencia del registro                              | Timestamp       |
| end_time       | Fecha de término de vigencia del registro                             | Timestamp       |
| report         | Indica si la conexión se incluye en los reportes (True/False)         | \-              |
| h_type         | Tipo de conexión (por ejemplo, 'canal', 'tubería', etc.)              | \-              |
| ini            | Nodo o embalse de inicio de la conexión                               | \-              |
| end            | Nodo o embalse final de la conexión                                   | \-              |
| h_max_flow     | Flujo máximo permitido por la conexión                                | Hm³/h o m³/s    |
| h_min_flow     | Flujo mínimo permitido por la conexión                                | Hm³/h o m³/s    |
| h_ramp         | Máxima variación de flujo permitida entre periodos consecutivos       | Hm³/h o m³/s    |
| h_delay        | Tiempo de retardo (delay) entre entrada y salida de flujo             | horas o bloques |
| h_delayed_q    | Caudal retrasado (ordenado por el retardo configurado en `h_delay`)   | Hm³/h o m³/s    |
| h_flow_penalty | Penalización asociada al flujo por la conexión (en caso de violación) | USD/Hm³         |

## `HydroGenerator `

| Columna                 | Descripción                                                    | Unidad     |
| ----------------------- | -------------------------------------------------------------- | ---------- |
| name                    | Nombre del generador hidroeléctrico                            | \-         |
| start_time              | Fecha de inicio de vigencia del registro                       | Timestamp  |
| end_time                | Fecha de término de vigencia del registro                      | Timestamp  |
| report                  | Indica si el generador se incluye en los reportes (True/False) | \-         |
| coordinates             | Coordenadas geográficas del generador                          | Lat, Lon   |
| connected               | Indica si está conectado al sistema (True/False)               | \-         |
| busbar                  | Barra eléctrica a la que está conectado                        | \-         |
| control_areas           | Áreas de control del generador                                 | \-         |
| hydro_group_name        | Nombre del grupo hidroeléctrico asociado                       | \-         |
| use_pump_mode           | Indica si puede operar en modo bombeo (True/False)             | \-         |
| pmax                    | Potencia máxima de generación                                  | MW         |
| pmin                    | Potencia mínima de generación                                  | MW         |
| pmax_pump               | Potencia máxima en modo bombeo                                 | MW         |
| pmin_pump               | Potencia mínima en modo bombeo                                 | MW         |
| pump_reserve_mode       | Modo de reserva en operación de bombeo                         | \-         |
| rpmax_up                | Máximo incremento en potencia en reserva primaria              | MW/h o MW  |
| rpmax_down              | Máximo decremento en potencia en reserva primaria              | MW/h o MW  |
| rsmax_up                | Máximo incremento en potencia en reserva secundaria            | MW/h o MW  |
| rsmax_down              | Máximo decremento en potencia en reserva secundaria            | MW/h o MW  |
| rtmax_up                | Máximo incremento en potencia en reserva terciaria             | MW/h o MW  |
| rtmax_down              | Máximo decremento en potencia en reserva terciaria             | MW/h o MW  |
| pcost_rp_up             | Costo por activar reserva primaria positiva                    | USD/MW     |
| pcost_rs_up             | Costo por activar reserva secundaria positiva                  | USD/MW     |
| pcost_rt_up             | Costo por activar reserva terciaria positiva                   | USD/MW     |
| pcost_rp_down           | Costo por activar reserva primaria negativa                    | USD/MW     |
| pcost_rs_down           | Costo por activar reserva secundaria negativa                  | USD/MW     |
| pcost_rt_down           | Costo por activar reserva terciaria negativa                   | USD/MW     |
| vomc_avg                | Costo operativo variable promedio (sin combustible)            | USD/MWh    |
| eff                     | Eficiencia de conversión hidráulica                            | \- (0-1)   |
| eff_poly                | Coeficientes de curva polinómica de eficiencia                 | \-         |
| eff_pump                | Eficiencia en modo bombeo                                      | \- (0-1)   |
| performance_curve       | Curva de rendimiento asociada                                  | \-         |
| use_performance_curve   | Indica si se usa la curva de rendimiento (True/False)          | \-         |
| auxserv                 | Consumo de servicios auxiliares                                | MW         |
| flex                    | Nivel de flexibilidad operativa                                | \-         |
| uc_linear               | Indica si la unidad está sujeta a compromiso unitario lineal   | True/False |
| rampup                  | Tasa máxima de incremento de potencia                          | MW/h       |
| rampdn                  | Tasa máxima de disminución de potencia                         | MW/h       |
| startcost               | Costo de arranque del generador                                | USD        |
| shutdncost              | Costo de detención del generador                               | USD        |
| mindntime               | Tiempo mínimo de detención                                     | horas      |
| minuptime               | Tiempo mínimo de operación                                     | horas      |
| is_ncre                 | Indica si es una fuente renovable no convencional              | True/False |
| forced_commit           | Define si debe permanecer encendido obligatoriamente           | True/False |
| initialstate            | Estado inicial (encendido/apagado)                             | 1/0        |
| initialtime             | Tiempo inicial del estado inicial                              | horas      |
| unavailability          | Factor de indisponibilidad                                     | % (0-1)    |
| use_ds71_2016           | Uso de norma de energía DS 71/2016 (Chile)                     | True/False |
| candidate               | Indica si es una unidad candidata a expansión                  | True/False |
| gen_recourse            | Indica si tiene recurso estocástico asociado                   | True/False |
| gen_recourse_start_time | Tiempo inicial del recurso asociado                            | Timestamp  |
| dimensioned             | Indica si las capacidades fueron dimensionadas                 | True/False |
| gen_inv_cost            | Costo de inversión asociado al generador                       | USD/MW     |
| initial_investment      | Inversión inicial total                                        | USD        |
| recog_pot               | Potencia reconocida (para facturación/ingresos)                | MW         |
| forced_outage_rate      | Tasa de fallas forzadas                                        | % (0-1)    |
| fom_cost                | Costo fijo de operación y mantenimiento                        | USD/MW-año |
| lifetime                | Vida útil esperada                                             | años       |
| inertia                 | Inercia asociada al generador                                  | MW·s       |
| voltage                 | Nivel de tensión del generador                                 | kV         |
| owner                   | Propietario o entidad dueña del generador                      | \-         |

## `HydroGroup `

| Columna    | Descripción                                                | Unidad    |
| ---------- | ---------------------------------------------------------- | --------- |
| name       | Nombre del grupo hidroeléctrico                            | \-        |
| start_time | Fecha de inicio de vigencia del registro                   | Timestamp |
| end_time   | Fecha de término de vigencia del registro                  | Timestamp |
| report     | Indica si el grupo se incluye en los reportes (True/False) | \-        |
| hg_sp_min  | Volumen mínimo permitido del grupo hidroeléctrico          | Hm³       |
| hg_sp_max  | Volumen máximo permitido del grupo hidroeléctrico          | Hm³       |

## `HydroNode `

| Columna       | Descripción                                               | Unidad    |
| ------------- | --------------------------------------------------------- | --------- |
| name          | Nombre del nodo hidroeléctrico                            | \-        |
| start_time    | Fecha de inicio de vigencia del registro                  | Timestamp |
| end_time      | Fecha de término de vigencia del registro                 | Timestamp |
| report        | Indica si el nodo se incluye en los reportes (True/False) | \-        |
| formulate_bal | Indica si se formula el balance hídrico (True/False)      | \-        |

## `Inflow `

| Columna         | Descripción                                                              | Unidad            |
| --------------- | ------------------------------------------------------------------------ | ----------------- |
| name            | Nombre del registro de afluencia                                         | \-                |
| start_time      | Fecha de inicio de vigencia del registro                                 | Timestamp         |
| end_time        | Fecha de término de vigencia del registro                                | Timestamp         |
| report          | Indica si este registro se incluye en los reportes (True/False)          | \-                |
| inflows_qm3     | Afluencias de agua en metros cúbicos por trimestre                       | m³/trim           |
| plp_indep_hydro | Indica si es hidrología independiente en Programación Lineal Estocástica | Booleano (-/True) |

## `Irrigation `

| Columna         | Descripción                                                          | Unidad            |
| --------------- | -------------------------------------------------------------------- | ----------------- |
| name            | Nombre del registro de riego                                         | \-                |
| start_time      | Fecha de inicio de vigencia del registro                             | Timestamp         |
| end_time        | Fecha de término de vigencia del registro                            | Timestamp         |
| report          | Indica si este registro se incluye en los reportes (True/False)      | \-                |
| irrigations_qm3 | Volumen de agua utilizada para riego en metros cúbicos por trimestre | m³/trim           |
| voli            | Volumen de influencia o índice relacionado al uso del agua           | \- (adimensional) |

## `Load `

| Columna         | Descripción                                                                | Unidad    |
| --------------- | -------------------------------------------------------------------------- | --------- |
| name            | Nombre del nodo de carga                                                   | \-        |
| start_time      | Fecha de inicio de vigencia del registro                                   | Timestamp |
| end_time        | Fecha de término de vigencia del registro                                  | Timestamp |
| report          | Indica si el registro se incluye en los reportes (True/False)              | \-        |
| busbar          | Barra eléctrica a la que está conectada la carga                           | \-        |
| connected       | Indica si la carga está activa/conectada (True/False)                      | \-        |
| demand          | Demanda eléctrica asociada al nodo                                         | MW        |
| projection_type | Tipo de proyección utilizada para estimar la demanda (por ejemplo, lineal) | \-        |
| voltage         | Nivel de tensión eléctrica del nodo                                        | kV        |
| voll            | Valor de energía no suministrada (Value of Lost Load)                      | USD/MWh   |
| owner           | Propietario del nodo de carga                                              | \-        |

## `LoadProjection`

| Columna    | Descripción                                                      | Unidad     |
| ---------- | ---------------------------------------------------------------- | ---------- |
| name       | Nombre del nodo de carga o escenario al que aplica la proyección | \-         |
| start_time | Fecha de inicio de vigencia del factor de proyección             | Timestamp  |
| end_time   | Fecha de término de vigencia del factor de proyección            | Timestamp  |
| report     | Indica si el registro se incluye en los reportes (True/False)    | \-         |
| factor     | Factor de proyección aplicado a la demanda base                  | \- (adim.) |

## `Profile`

| Columna    | Descripción                                                              | Unidad    |
| ---------- | ------------------------------------------------------------------------ | --------- |
| name       | Nombre del perfil de potencia aplicado (por ejemplo, a una planta o ESS) | \-        |
| start_time | Fecha y hora de inicio de vigencia del perfil                            | Timestamp |
| end_time   | Fecha y hora de término de vigencia del perfil                           | Timestamp |
| report     | Indica si el registro se incluye en los reportes (True/False)            | \-        |
| power      | Potencia asociada al perfil en cada instante                             | MW        |

## `PvGenerator`

| Columna                 | Descripción                                                           | Unidad     |
| ----------------------- | --------------------------------------------------------------------- | ---------- |
| name                    | Nombre del generador fotovoltaico                                     | \-         |
| start_time              | Fecha y hora de inicio de operación o vigencia del registro           | Timestamp  |
| end_time                | Fecha y hora de finalización de operación o vigencia del registro     | Timestamp  |
| report                  | Indica si el registro se incluye en los reportes (True/False)         | \-         |
| coordinates             | Coordenadas geográficas del generador                                 | Lat, Long  |
| connected               | Indica si el generador está conectado a la red                        | True/False |
| busbar                  | Barra eléctrica a la que está conectado el generador                  | \-         |
| control_areas           | Área(s) de control donde opera el generador                           | \-         |
| zone                    | Zona de soporte a la que está asociado el generador                   | \-         |
| pmax                    | Potencia máxima del generador                                         | MW         |
| pmin                    | Potencia mínima del generador                                         | MW         |
| rpmax_up                | Capacidad máxima de reserva primaria hacia arriba                     | MW         |
| rpmax_down              | Capacidad máxima de reserva primaria hacia abajo                      | MW         |
| rsmax_up                | Capacidad máxima de reserva secundaria hacia arriba                   | MW         |
| rsmax_down              | Capacidad máxima de reserva secundaria hacia abajo                    | MW         |
| rtmax_up                | Capacidad máxima de reserva terciaria hacia arriba                    | MW         |
| rtmax_down              | Capacidad máxima de reserva terciaria hacia abajo                     | MW         |
| pcost_rp_up             | Costo de proveer reserva primaria hacia arriba                        | \$/MW      |
| pcost_rs_up             | Costo de proveer reserva secundaria hacia arriba                      | \$/MW      |
| pcost_rt_up             | Costo de proveer reserva terciaria hacia arriba                       | \$/MW      |
| pcost_rp_down           | Costo de proveer reserva primaria hacia abajo                         | \$/MW      |
| pcost_rs_down           | Costo de proveer reserva secundaria hacia abajo                       | \$/MW      |
| pcost_rt_down           | Costo de proveer reserva terciaria hacia abajo                        | \$/MW      |
| vomc_avg                | Costo variable promedio de operación y mantenimiento                  | \$/MWh     |
| auxserv                 | Servicios auxiliares asociados al generador                           | \-         |
| flex                    | Indica si el generador es flexible                                    | True/False |
| is_ncre                 | Indica si el generador es de energía renovable no convencional (ERNC) | True/False |
| forced_commit           | Indica si la unidad está forzada a operar                             | True/False |
| unavailability          | Porcentaje de indisponibilidad del generador                          | %          |
| candidate               | Indica si la unidad es candidata para inversión o expansión           | True/False |
| gen_recourse            | Indica si hay reconsideración económica en la operación               | True/False |
| gen_recourse_start_time | Tiempo desde cuando inicia la reconsideración económica               | Timestamp  |
| dimensioned             | Indica si la unidad está dimensionada                                 | True/False |
| gen_inv_cost            | Costo de inversión por unidad instalada                               | \$/MW      |
| initial_investment      | Inversión inicial en el generador                                     | \$         |
| recog_pot               | Potencia reconocida del generador                                     | MW         |
| forced_outage_rate      | Tasa de falla forzada del generador                                   | %          |
| fom_cost                | Costo fijo de operación y mantenimiento                               | \$/MW⋅año  |
| lifetime                | Vida útil del generador                                               | años       |
| inertia                 | Inercia proporcionada por el generador                                | MW·s       |
| voltage                 | Nivel de tensión al que se conecta el generador                       | kV         |
| owner                   | Propietario o empresa dueña del activo                                | \-         |

## `System`

| Columna               | Descripción                                                                        | Unidad          |
| --------------------- | ---------------------------------------------------------------------------------- | --------------- |
| name                  | Nombre del sistema o escenario                                                     | \-              |
| sbase                 | Base de potencia del sistema, utilizada como referencia para cálculos eléctricos   | MVA             |
| busbar_ref            | Barra de referencia o barra slack del sistema                                      | \-              |
| interest_rate         | Tasa de interés o descuento utilizada para inversiones                             | % anual         |
| adequacy_margin       | Margen de suficiencia de capacidad requerido sobre la demanda máxima               | %               |
| obj_scaling           | Factor de escalamiento aplicado a la función objetivo                              | \-              |
| dams_scaling          | Factor de escalamiento aplicado a las variables de embalses                        | \-              |
| beta_loads            | Factor de penalización o costo asociado al desabastecimiento de carga              | \$/MWh          |
| beta_irrigations      | Factor de penalización asociado al incumplimiento de demandas de riego             | \$/m³           |
| minihydro_power_limit | Límite de potencia máxima para mini-hidroeléctricas                                | MW              |
| minihydro_date_limit  | Fecha límite de operación de las mini-hidroeléctricas                              | Timestamp       |
| co2_emission_tax      | Impuesto por tonelada de CO₂ emitida                                               | \$/ton CO₂      |
| cap_payments          | Pagos por capacidad a generadores participantes                                    | \$/MW⋅año       |
| ncre_quota            | Cuota obligatoria de participación de Energías Renovables No Convencionales (ERNC) | % energía anual |

## `ThermalGenerator`

| Columna                 | Descripción                                                         | Unidad      |
| ----------------------- | ------------------------------------------------------------------- | ----------- |
| name                    | Nombre del generador térmico                                        | \-          |
| start_time              | Tiempo de inicio del periodo de operación                           | Timestamp   |
| end_time                | Tiempo de fin del periodo de operación                              | Timestamp   |
| report                  | Indicador si el generador se incluye en los reportes                | Boolean     |
| coordinates             | Coordenadas geográficas del generador                               | Lat/Lon     |
| connected               | Indica si el generador está conectado físicamente al sistema        | Boolean     |
| busbar                  | Barra eléctrica del sistema a la que está conectado                 | \-          |
| control_areas           | Área(s) de control a la que pertenece                               | \-          |
| pmax                    | Potencia máxima que puede generar                                   | MW          |
| pmin                    | Potencia mínima que debe generar                                    | MW          |
| rpmax_up                | Reserva primaria máxima disponible al alza                          | MW          |
| rpmax_down              | Reserva primaria máxima disponible a la baja                        | MW          |
| rsmax_up                | Reserva secundaria máxima disponible al alza                        | MW          |
| rsmax_down              | Reserva secundaria máxima disponible a la baja                      | MW          |
| rtmax_up                | Reserva terciaria máxima disponible al alza                         | MW          |
| rtmax_down              | Reserva terciaria máxima disponible a la baja                       | MW          |
| pcost_rp_up             | Costo por MW de reserva primaria al alza                            | \$/MW       |
| pcost_rs_up             | Costo por MW de reserva secundaria al alza                          | \$/MW       |
| pcost_rt_up             | Costo por MW de reserva terciaria al alza                           | \$/MW       |
| pcost_rp_down           | Costo por MW de reserva primaria a la baja                          | \$/MW       |
| pcost_rs_down           | Costo por MW de reserva secundaria a la baja                        | \$/MW       |
| pcost_rt_down           | Costo por MW de reserva terciaria a la baja                         | \$/MW       |
| vomc_avg                | Costo variable promedio de operación y mantenimiento                | \$/MWh      |
| heatrate_avg            | Tasa de consumo de combustible por unidad de energía generada       | MMBtu/MWh   |
| cost_function           | Función de costo definida para el generador                         | \-          |
| auxserv                 | Consumo auxiliar del generador                                      | MW          |
| flex                    | Indica si el generador es flexible                                  | Boolean     |
| uc_linear               | Control unit commitment con formulación lineal                      | Boolean     |
| rampup                  | Tasa máxima de aumento de la generación                             | MW/h        |
| rampdn                  | Tasa máxima de disminución de la generación                         | MW/h        |
| faststart               | Indica si el generador puede realizar arranque rápido               | Boolean     |
| startcost               | Costo de arranque del generador                                     | \$/arranque |
| shutdncost              | Costo de apagado del generador                                      | \$/apagado  |
| mindntime               | Tiempo mínimo que debe permanecer apagado después de apagarse       | h           |
| minuptime               | Tiempo mínimo que debe permanecer encendido después de arrancar     | h           |
| is_ncre                 | Indica si es una fuente de energía renovable no convencional (ERNC) | Boolean     |
| forced_commit           | Indica si el generador debe estar comprometido obligatoriamente     | Boolean     |
| initialstate            | Estado inicial del generador (encendido o apagado)                  | 0/1         |
| initialtime             | Tiempo que ha estado en el estado inicial                           | h           |
| fuel_name               | Nombre del combustible utilizado                                    | \-          |
| unavailability          | Tasa de indisponibilidad del generador                              | %           |
| co2_emission            | Emisiones de CO₂ por unidad de energía generada                     | ton/MWh     |
| candidate               | Indica si es una unidad candidata a construcción                    | Boolean     |
| gen_recourse            | Indica si tiene recourse para optimización estocástica              | Boolean     |
| gen_recourse_start_time | Tiempo en el que comienza a aplicar la lógica de recourse           | Timestamp   |
| dimensioned             | Indica si está dimensionado en capacidad                            | Boolean     |
| gen_inv_cost            | Costo de inversión por unidad de capacidad instalada                | \$/MW       |
| initial_investment      | Costo fijo de inversión inicial                                     | \$          |
| recog_pot               | Potencial de recuperación de inversión en potencia                  | \-          |
| forced_outage_rate      | Tasa de fallas forzadas                                             | %           |
| fom_cost                | Costo fijo anual de operación y mantenimiento                       | \$/MW⋅año   |
| lifetime                | Vida útil esperada de la unidad                                     | años        |
| inertia                 | Contribución del generador a la inercia del sistema                 | MW⋅s        |
| voltage                 | Nivel de tensión en el punto de conexión                            | kV          |
| owner                   | Propietario o empresa operadora                                     | \-          |

## `WindGenerator`

| Columna                 | Descripción                                                         | Unidad    |
| ----------------------- | ------------------------------------------------------------------- | --------- |
| name                    | Nombre del parque o turbina eólica                                  | \-        |
| start_time              | Tiempo de inicio del periodo de operación                           | Timestamp |
| end_time                | Tiempo de fin del periodo de operación                              | Timestamp |
| report                  | Indicador si el generador se incluye en los reportes                | Boolean   |
| coordinates             | Coordenadas geográficas del generador                               | Lat/Lon   |
| connected               | Indica si el generador está conectado físicamente al sistema        | Boolean   |
| busbar                  | Barra eléctrica del sistema a la que está conectado                 | \-        |
| control_areas           | Área(s) de control a la que pertenece                               | \-        |
| zone                    | Zona geográfica o climatológica del parque eólico                   | \-        |
| pmax                    | Potencia máxima que puede generar                                   | MW        |
| pmin                    | Potencia mínima que debe generar                                    | MW        |
| rpmax_up                | Reserva primaria máxima disponible al alza                          | MW        |
| rpmax_down              | Reserva primaria máxima disponible a la baja                        | MW        |
| rsmax_up                | Reserva secundaria máxima disponible al alza                        | MW        |
| rsmax_down              | Reserva secundaria máxima disponible a la baja                      | MW        |
| rtmax_up                | Reserva terciaria máxima disponible al alza                         | MW        |
| rtmax_down              | Reserva terciaria máxima disponible a la baja                       | MW        |
| pcost_rp_up             | Costo por MW de reserva primaria al alza                            | \$/MW     |
| pcost_rs_up             | Costo por MW de reserva secundaria al alza                          | \$/MW     |
| pcost_rt_up             | Costo por MW de reserva terciaria al alza                           | \$/MW     |
| pcost_rp_down           | Costo por MW de reserva primaria a la baja                          | \$/MW     |
| pcost_rs_down           | Costo por MW de reserva secundaria a la baja                        | \$/MW     |
| pcost_rt_down           | Costo por MW de reserva terciaria a la baja                         | \$/MW     |
| vomc_avg                | Costo variable promedio de operación y mantenimiento                | \$/MWh    |
| auxserv                 | Consumo auxiliar del generador                                      | MW        |
| flex                    | Indica si el generador es flexible                                  | Boolean   |
| is_ncre                 | Indica si es una fuente de energía renovable no convencional (ERNC) | Boolean   |
| forced_commit           | Indica si el generador debe estar comprometido obligatoriamente     | Boolean   |
| unavailability          | Tasa de indisponibilidad del generador                              | %         |
| candidate               | Indica si es una unidad candidata a construcción                    | Boolean   |
| gen_recourse            | Indica si tiene recourse para optimización estocástica              | Boolean   |
| gen_recourse_start_time | Tiempo en el que comienza a aplicar la lógica de recourse           | Timestamp |
| dimensioned             | Indica si está dimensionado en capacidad                            | Boolean   |
| gen_inv_cost            | Costo de inversión por unidad de capacidad instalada                | \$/MW     |
| initial_investment      | Costo fijo de inversión inicial                                     | \$        |
| recog_pot               | Potencial de recuperación de inversión en potencia                  | \-        |
| forced_outage_rate      | Tasa de fallas forzadas                                             | %         |
| fom_cost                | Costo fijo anual de operación y mantenimiento                       | \$/MW⋅año |
| lifetime                | Vida útil esperada de la unidad                                     | años      |
| inertia                 | Contribución del generador a la inercia del sistema                 | MW⋅s      |
| voltage                 | Nivel de tensión en el punto de conexión                            | kV        |
| owner                   | Propietario o empresa operadora                                     | \-        |
