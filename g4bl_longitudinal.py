import numpy
import shutil
import os
import subprocess
import xboa.hit
import xboa.bunch

class Setup():
    def __init__(self):
        pass

    def setup(self, config):
        for key, value in config.items():
            if key not in self.__dict__:
                raise KeyError("Did not recognise cavity configuration", item)
            if self.__dict__[key] is not None:
                value = type(self.__dict__[key])(value)
            self.__dict__[key] = value

class Cavity(Setup):
    def __init__(self):
        self.name = ""
        self.inner_length = 0.0
        self.frequency = 0.0
        self.max_gradient = 0.0
        self.z_position = 0.0
        self.phase = None
        self.time_offset = None

    def build(self):
        my_cavity = """
pillbox {0} innerLength={1} frequency={2} \\
    maxGradient={3} irisRadius=100.0 \\
    win1Thick=0.0 win2Thick=0.0 wallThick=0.0 collarThick=0.0 \\
    kill=1 maxStep=0.1 innerRadius=500.0""".format(self.name, self.inner_length, self.frequency, self.max_gradient, self.time_offset)
        if self.phase is not None:
            my_cavity += f" phaseAcc={self.phase}"
        if self.time_offset is not None:
            my_cavity += f" timeOffset={self.phase}"
        my_cavity += f"\nplace {self.name} z={self.z_position} color=1,0,0\n"
        return my_cavity

class Reference(Setup):
    def __init__(self):
        self.particle = "mu+"
        self.p_start = 100.0
        self.z_start = 0.0
        self.t_start = 0.0
        self.no_e_field = 0
        self.no_e_loss = 0

    def build(self):
        my_reference = \
            f"reference particle={self.particle} referenceMomentum={self.p_start} "+\
            f" beamZ={self.z_start} beamX=0.0 beamT={self.t_start} "+\
            f"noEfield={self.no_e_field} noEloss={self.no_e_loss}"
        return my_reference

class Beam(Setup):
    def __init__(self):
        self.filename = ""
        self.out_dir = ""
        self.pid = -13
        self.beam_z = 0.0
        self.beams = []
        self.particles = []

    def build(self):
        self.build_beam_file()
        my_beam = """
beam ascii particle={0} nEvents={1} filename={2} format=BLTrackFile beamZ={3}
""".format(self.pid, len(self.particles), self.filename, self.beam_z)
        return my_beam

    def build_beam_file(self):
        self.particles = []
        for a_beam in self.beams:
            self.build_a_beam(a_beam)
        bunch = xboa.bunch.Bunch.new_from_hits(self.particles)
        bunch.hit_write_builtin("g4beamline_bl_track_file", os.path.join(self.out_dir, self.filename))

    def build_a_beam(self, a_beam):
        beam_type = a_beam["type"]
        beam_builder = {
            "longitudinal_grid":self.longitudinal_grid,
        }[beam_type]
        beam_builder(a_beam)

    def my_linspace(self, start, stop, num):
        if num == 1:
            return [(start+stop)/2]
        else:
            return numpy.linspace(start, stop, num).tolist()

    def longitudinal_grid(self, a_beam):
        t_list = self.my_linspace(a_beam["t_min"], a_beam["t_max"], a_beam["n_t_steps"])
        e_list = self.my_linspace(a_beam["e_min"], a_beam["e_max"], a_beam["n_e_steps"])
        mass = xboa.common.pdg_pid_to_mass[abs(self.pid)]
        for t in t_list:
            for e in e_list:
                hit_dict = {"pid":self.pid, "mass":mass, "t":t, "energy":e+mass, "event_number":len(self.particles)+1}
                self.particles.append(xboa.hit.Hit.new_from_dict(hit_dict, "pz"))

class G4BLExecution:
    def __init__(self, linac):
        self.g4bl_path = os.path.expandvars("${HOME}/Software/install/bin/g4bl")
        self.lattice_filename = linac.lattice_filename
        self.linac = linac
        self.guess_logfile()
        self.command_line = []

    def guess_logfile(self):
        out_dir = self.linac.out_dir()
        self.log_filename = os.path.join(out_dir, "log")

    def execute(self):
        command = [self.g4bl_path, os.path.split(self.lattice_filename)[1]]
        cwd = os.getcwd()
        os.chdir(self.linac.out_dir())
        print("Running", command, "in", os.getcwd())
        with open("log", "w") as logfile:
            proc = subprocess.run(
                    command,
                    stdout=logfile, stderr=subprocess.STDOUT)
        print("   ... completed with return code", proc.returncode)
        os.chdir(cwd)
        if proc.returncode:
            raise RuntimeError("G4BL did not execute successfully")

class G4BLLinac:
    def __init__(self, lattice_filename):
        self.lattice_file = None
        self.lattice_filename = lattice_filename
        self.rf_cavities = []
        self.reference = {}
        self.beam = {"filename":os.path.join(self.out_dir(), "beam.txt")}
        self.do_stochastics=1
        self.z_spacing = 100.0 # mm
        self.min_z = 0.0 # mm
        self.max_z = 10000.0 # mm
        self.max_step = 100.0 # mm
        self.eps_max = 0.01
        self.output_file = "output_data" # g4bl puts this in the run directory and adds ".txt" as suffix
        self.cleanup_dir = True

    def out_dir(self):
        return os.path.split(self.lattice_filename)[0]

    def build_topmatter(self):
        topmatter = f"physics default doStochastics={self.do_stochastics}\n"
        topmatter += f"zntuple cooling_monitor zloop={self.min_z}:{self.max_z}:{self.z_spacing} format=for009 file=output_data coordinates=c\n"
        topmatter += f"param epsMax={self.eps_max}\n" # g4bl bug
        topmatter += f"param maxStep={self.max_step}\n" # g4bl bug
        self.lattice_file.write(topmatter)

    def build_reference(self):
        my_reference = Reference()
        my_reference.setup(self.reference)
        ref_string = my_reference.build()
        self.lattice_file.write(ref_string)

    def build_beam(self):
        my_beam = Beam()
        my_beam.setup(self.beam)
        beam_string = my_beam.build()
        self.lattice_file.write(beam_string)

    def build_rf(self):
        for cavity in self.rf_cavities:
            my_cavity = Cavity()
            my_cavity.setup(cavity)
            cavity_string = my_cavity.build()
            self.lattice_file.write(cavity_string)

    def build_linac(self):
        clean_dir(self.out_dir(), self.cleanup_dir)
        with open(self.lattice_filename, "w") as self.lattice_file:
            self.build_topmatter()
            self.build_reference()
            self.build_beam()
            self.build_rf()

def clean_dir(my_dir, cleanup):
    if os.path.exists(my_dir):
        if cleanup:
            shutil.rmtree(my_dir)
        else:
            return
    os.makedirs(my_dir)
