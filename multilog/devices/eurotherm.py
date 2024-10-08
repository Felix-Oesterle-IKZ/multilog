from copy import deepcopy
import datetime
import logging
import numpy as np
from serial import Serial, SerialException
import yaml
import socket
import json

logger = logging.getLogger(__name__)


class SerialMock:
    """This class is used to mock a serial interface for debugging purposes."""

    def write(self, _):
        pass

    def readline(self):
        return "".encode()


class Eurotherm:
    def __init__(self, config, name="Eurotherm"):
        """Prepare sampling.

        Args:
            config (dict): device configuration (as defined in
                config.yml in the devices-section).
            name (str, optional): device name.
        """
        logger.info(f"Initializing Eurotherm device '{name}'")
        self.config = config
        self.name = name
        
        if self.config.get("serial-interface") != None: # serial conection
            self.conectionType = "serial"
            self.read_temperature = "\x040000PV\x05"
            self.read_op          = "\x040000OP\x05"
            self.meas_data = {"Temperature": [], "Operating point": []}
            try:
                self.serial = Serial(**config["serial-interface"])
            except SerialException as e:
                logger.exception(f"Connection to {self.name} not possible.")
                self.serial = SerialMock()
                
        elif self.config.get("tcp-interface") != None: # tcp conection
            self.conectionType = "tcp"
            self.vifconIP      = config["tcp-interface"]["IP"]
            self.vifconPort    = config["tcp-interface"]["Port"]
            self.meas_data = {"IWT": [], "SWT": [], "Operating point": []}
            try:
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.s.connect((self.vifconIP, self.vifconPort))
                logger.info(f"{self.name} connected to VIFCON")
            except Exception as e:
                logger.exception(f"Connection to {self.name} not possible.")

        

        

    def sample(self):
        """Read sampling form device.

        Returns:
            dict: {sensor name: measurement value}
        """
        if self.conectionType == "serial":
            try:
                self.serial.write(self.read_temperature.encode())
                temperature = float(self.serial.readline().decode()[3:-2])
                self.serial.write(self.read_op.encode())
                op = float(self.serial.readline().decode()[3:-2])
            except Exception as e:
                logger.exception(f"Could not sample Eurotherm.")
                temperature = np.nan
                op = np.nan
            return {"Temperature": temperature, "Operating point": op}
                
        elif self.conectionType == "tcp":
            try:
                self.s.send(bytes(self.name, 'UTF-8')) # send trigger
                received = self.s.recv(1024)
                received = received.decode("utf-8")
                data = json.loads(received)
                IWT = data["IWT"]
                SWT = data["SWT"]
                op  = data["IWOp"]
            except Exception as e:
                logger.exception(f"Could not sample {self.name}.")
                IWT = np.nan
                SWT = np.nan
                op  = np.nan
            return {"IWT": IWT, "SWT": SWT, "Operating point": op}
        

    def save_measurement(self, time_abs, time_rel, sampling):
        """Write measurement data to file.

        Args:
            time_abs (datetime): measurement timestamp.
            time_rel (float): relative time of measurement.
            sampling (dict): sampling data, as returned from sample()
        """
        timediff = (
            datetime.datetime.now(datetime.timezone.utc).astimezone() - time_abs
        ).total_seconds()
        if timediff > 1:
            logger.warning(
                f"{self.name} save_measurement: time difference between event and saving of {timediff} seconds for samplint timestep {time_abs.isoformat(timespec='milliseconds').replace('T', ' ')} - {time_rel}"
            )
            
        self.meas_data["Operating point"].append(sampling["Operating point"])
        if self.conectionType == "serial":
            self.meas_data["Temperature"].append(sampling["Temperature"])
            line = f"{time_abs.isoformat(timespec='milliseconds').replace('T', ' ')},{time_rel},{sampling['Temperature']},{sampling['Operating point']},\n"
        elif self.conectionType == "tcp":
            self.meas_data["IWT"].append(sampling["IWT"])
            self.meas_data["SWT"].append(sampling["SWT"])
            line = f"{time_abs.isoformat(timespec='milliseconds').replace('T', ' ')},{time_rel},{sampling['IWT']},{sampling['SWT']},{sampling['Operating point']},\n"
        
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(line)

    def init_output(self, directory="./"):
        """Initialize the csv output file.

        Args:
            directory (str, optional): Output directory. Defaults to "./".
        """
        self.filename = f"{directory}/{self.name}.csv"
        
        if self.conectionType == "serial":
            units = "# datetime,s,DEG C,-,\n"
            header = "time_abs,time_rel,Temperature,Operating point,\n"
        elif self.conectionType == "tcp":
            units = "# datetime,s,DEG C,DEG C,-,\n"
            header = "time_abs,time_rel,IWT,SWT,Operating point,\n"
            
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(units)
            f.write(header)
        self.write_nomad_file(directory)

    def write_nomad_file(self, directory="./"):
        """Write .archive.yaml file based on device configuration.

        Args:
            directory (str, optional): Output directory. Defaults to "./".
        """
        with open("./multilog/nomad/archive_template_sensor.yml") as f:
            nomad_template = yaml.safe_load(f)
        definitions = nomad_template.pop("definitions")
        data = nomad_template.pop("data")
        sensor_schema_template = nomad_template.pop("sensor_schema_template")
        data.update(
            {
                "data_file": self.filename.split("/")[-1],
            }
        )
        for sensor_name in self.meas_data:
            sensor_name_nomad = sensor_name.replace(" ", "_").replace("-", "_")
            data.update(
                {
                    sensor_name_nomad: {
                        # "model": "your_field_here",
                        # "name": sensor_name_nomad,
                        # "sensor_id": sensor_name.split(" ")[0],
                        # "attached_to": sensor_name, # TODO this information is important!
                        # "measured_property": ,
                        # "type": sensor_type,
                        # "notes": "TE_1_K air 155 mm over crucible",
                        # "unit": self.unit[sensor_name],  # TODO
                        "value_timestamp_rel": "#/data/value_timestamp_rel",
                        "value_timestamp_abs": "#/data/value_timestamp_abs",
                    }
                }
            )
            if "comment" in self.config:
                data[sensor_name_nomad].update({"comment": self.config["comment"]})
            sensor_schema = deepcopy(sensor_schema_template)
            sensor_schema["section"]["quantities"]["value_log"]["m_annotations"][
                "tabular"
            ]["name"] = sensor_name
            definitions["sections"]["Sensors_list"]["sub_sections"].update(
                {sensor_name_nomad: sensor_schema}
            )
        nomad_dict = {
            "definitions": definitions,
            "data": data,
        }
        with open(f"{directory}/{self.name}.archive.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(nomad_dict, f, sort_keys=False)

    def getConectionType(self):
        return self.conectionType
