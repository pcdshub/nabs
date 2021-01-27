import matplotlib.pyplot as plt
import numpy as np
from .plan_stubs import get_sample_info, snake_grid_list


def show_shot_targets(sample_name, path, snake_like=True):
    """
    Display a plot with targets.

    This class is used in conjunction witht the `XYGridStage` object from
    `pcdsdevices` as well as the `fixed_target_scan` from `nabs.plans`.
    It displays a scatter plot with the targets that have been scanned (& shot)
    with `fixed_target_scan`, and the targets that are still available.
    It uses the information saved in an yaml file for a specific sample
    to get the x and y positions as well as the last target that has been shot.
    This information is saved with the help of the `XYGridStage` object.

    Parameters
    ----------
    sample_name : str
        The name of the sample file to plot the graph for.
    path : str
        The path of the sample file.
    snake_like : bool
        Indicates if the targets have been shot in a snake_like pattern.
        Defaults to `True`.
        TODO this is a bad assumption - but most likely they will be
        shot in a snake-like pattern....
    """
    plt.clf()
    m_points, n_points, last_shot_index, xx, yy = get_sample_info(sample_name,
                                                                  path)

    # plot it in terms of M and N points (rows and columns)
    x = np.linspace(1, n_points, n_points)
    y = np.linspace(1, m_points, m_points)
    xm, ym = np.meshgrid(x, y)

    x_temp = xm.flatten()
    y_temp = ym.flatten()
    # snake_like:
    if snake_like:
        x_temp = snake_grid_list(np.array(x_temp).reshape(m_points, n_points))

    show_last_shot = True
    if last_shot_index == -1:
        # all should be available
        x_available = x_temp
        y_available = y_temp
        x_shot, y_shot = [], []
        show_last_shot = False
    else:
        x_available = x_temp[last_shot_index:]
        y_available = y_temp[last_shot_index:]
        x_shot = x_temp[:last_shot_index]
        y_shot = y_temp[:last_shot_index]

    plt.plot(x_available, y_available, 'o', color='blue', markersize=1,
             label="available")
    plt.plot(x_shot, y_shot, 'o', color='orange', markersize=1, label="shot")
    # invert the axis to reflect the experiment setup
    plt.gca().invert_yaxis()
    plt.xlabel('X Targets (N)')
    plt.ylabel('Y Targets (M)')
    if show_last_shot:
        plt.plot(x_temp[last_shot_index], y_temp[last_shot_index],
                 '*', color='red', markersize=2, label='last shot index')
        last_shot_pos = xx[last_shot_index], yy[last_shot_index]

        plt.annotate(f" {last_shot_pos[0]}\n {last_shot_pos[1]}",
                     (x_temp[last_shot_index], y_temp[last_shot_index]),
                     size=8, color='red')

    plt.legend(bbox_to_anchor=(0.15, -0.05), loc='upper center', ncol=3)
    plt.show()
